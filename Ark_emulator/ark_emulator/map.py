"""Map model and pathfinding for the battle simulation.

Implements the game's flow-field approach (see docs 05_movement_routes.md):
for each route segment we run a *four-neighbour* SPFA backward from the
target tile, then smooth only ``nextNode`` with the game's conservative
Bresenham line test.  The SPFA distance remains cardinal/Manhattan even when
the smoothed pointer lets an enemy move diagonally.  This distinction is
important for targeting formulas that consume ``distToFinal``.

Tile keys of interest: tile_end (blue door), tile_forbidden (unpassable),
tile_road (walkable), tile_hole (pit), tile_telin/tile_telout (teleport).
"""

from collections import deque

from .consts import MotionMask


class TileData:
    """Static tile definition from level mapData.tiles."""

    __slots__ = ("tile_key", "height_type", "buildable_type", "passable_mask",
                 "advanced_buildable_mask", "index", "_passable_override",
                 "_base_passable_mask", "_overlap_enabled",
                 "_buildable_override", "_base_buildable_type",
                 "_advanced_buildable_override")

    def __init__(self, index, raw=None):
        raw = raw or {}
        self.index = index
        self.tile_key = raw.get("tileKey") or "tile_unknown"
        self.height_type = raw.get("heightType")
        self.buildable_type = raw.get("buildableType")  # 1=melee 2=ranged
        self.passable_mask = raw.get("passableMask")
        self.advanced_buildable_mask = raw.get("advancedBuildableMask")
        self._buildable_override = None
        self._base_buildable_type = self.buildable_type
        self._advanced_buildable_override = None
        self._passable_override = None
        self._base_passable_mask = self.passable_mask
        self._overlap_enabled = False

    def passable(self, motion_mode):
        """motion_mode: 0=walk 1=fly (consts.MotionMode).

        Runtime RewriteTileOptions can override the mask (e.g.
        "\u884c\u661f\u788e\u5c51" makes its tile impassable); the override
        is cleared on restore."""
        mask = self._passable_override
        if mask is None:
            mask = self.passable_mask
        # Route gates/teleports are traversable endpoints even though the
        # exported tile definition can carry passableMask=0.
        if self.tile_key in ("tile_start", "tile_end", "tile_telin",
                             "tile_telout"):
            return True
        if mask is None:
            return True
        return bool(mask & (MotionMask.WALK_ONLY if motion_mode == 0
                            else MotionMask.FLY_ONLY))

    def set_passable_override(self, mask):
        """Apply a runtime passable-mask override (None clears it)."""
        if mask is None:
            self._passable_override = None
        else:
            self._passable_override = int(mask)
        self.passable_mask = self._passable_override             if self._passable_override is not None else self._base_passable_mask

    def set_buildable_override(self, mask):
        """Apply a runtime buildable-mask override (None restores the
        level's base buildableType). RewriteTileOptionsInRange uses this
        for enemies that make tiles undeployable in their range."""
        if mask is None:
            self._buildable_override = None
            return self._base_buildable_type
        self._buildable_override = int(mask)
        return self._buildable_override

    def set_advanced_buildable_override(self, mask):
        """Apply a runtime advancedBuildableMask override (night-map
        mechanic: DEFAULT <-> NIGHT when a lantern is lit/extinguished).
        None restores the level's base value. State + observer only:
        deploy gating by advanced masks is not modelled yet."""
        if mask is None:
            self._advanced_buildable_override = None
            return self.advanced_buildable_mask
        self._advanced_buildable_override = int(mask)
        return self._advanced_buildable_override

    @property
    def is_end(self):
        return self.tile_key == "tile_end"

    @property
    def is_hole(self):
        return self.tile_key == "tile_hole"

    @property
    def is_forbidden(self):
        return self.tile_key == "tile_forbidden"

    def to_dict(self):
        return {
            "tileKey": self.tile_key,
            "heightType": self.height_type,
            "buildableType": self.buildable_type,
            "passableMask": self.passable_mask,
            "advancedBuildableMask": (self._advanced_buildable_override
                                      if self._advanced_buildable_override
                                      is not None
                                      else self.advanced_buildable_mask),
        }


def materialize_tiles(rows, cols, raw_tiles, cells=None):
    """Create top-based row-major ``TileData`` objects.

    Official maps expose a bottom-based tile-definition list plus a spatial
    ``cells`` lookup.  Custom levels normally provide an already-spatial tile
    list and omit ``cells``.
    """
    source = list(raw_tiles or [])
    lookup = list(cells or [])
    expected = int(rows or 0) * int(cols or 0)
    if len(lookup) == expected and source:
        ordered = []
        for cell in lookup:
            try:
                tile_idx = int(cell)
            except (TypeError, ValueError):
                tile_idx = -1
            ordered.append(source[tile_idx]
                           if 0 <= tile_idx < len(source) else {})
    else:
        ordered = source
    return [TileData(i, tile) for i, tile in enumerate(ordered)]


class GameMap:
    """Grid map with tile lookup and flow-field pathfinding cache.

    Coordinates: row 0 at top, col 0 at left (row-major cell order).
    """

    def __init__(self, rows, cols, tiles):
        self.rows = rows
        self.cols = cols
        self.tiles = list(tiles)
        self.end_tiles = []
        for i, t in enumerate(self.tiles):
            if t.is_end:
                self.end_tiles.append(i)
        # Raw SPFA fields are independent of allowDiagonalMove; the latter
        # affects only the smoothed next-node pointers.
        self._raw_next_map = {}  # (motion_mode, target_idx) -> list[int]
        self._raw_dist_map = {}  # same key -> list[float]
        self._next_map = {}      # (..., allow_diag) -> smoothed list[int]
        self._dist_map = {}      # compatibility cache, points at raw dist
        self._edge_blocked = {}  # (src_idx, dir4) -> bool (from blockEdges)
        self._revision = 0

    @property
    def revision(self):
        return self._revision

    # ---- helpers ----
    def idx(self, row, col):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return -1
        return row * self.cols + col

    def rc(self, idx):
        return divmod(idx, self.cols)

    def tile(self, row, col):
        i = self.idx(row, col)
        return self.tiles[i] if i >= 0 else None

    def neighbors(self, idx, motion_mode, allow_diagonal=False):
        """Yield reverse-SPFA candidates in the game's U/R/D/L order.

        ``allow_diagonal`` is retained for API compatibility but deliberately
        ignored: diagonal travel is introduced only by next-node smoothing.
        """
        r, c = self.rc(idx)
        dirs = ((-1, 0, 1.0), (0, 1, 1.0),
                (1, 0, 1.0), (0, -1, 1.0))
        for dr, dc, cost in dirs:
            nr, nc = r + dr, c + dc
            ni = self.idx(nr, nc)
            if ni < 0:
                continue
            t = self.tiles[ni]
            # Reverse search expands *from* the target.  Official start/end
            # gates often have passableMask=0 but are valid route endpoints;
            # let the field leave those source nodes while still preventing
            # ordinary paths from entering forbidden terrain.
            if not t.passable(motion_mode) or t.is_forbidden:
                continue
            # This is a reverse search: the candidate ``ni`` walks toward
            # ``idx``, so check candidate -> centre rather than centre ->
            # candidate for directional edges.
            if self._edge_blocked.get((ni, _dir4(-dr, -dc))):
                continue
            yield ni, cost, bool(dr and dc)

    def _path_cost(self, idx, motion_mode):
        """Cost paid when SPFA enters a candidate tile.

        Holes are obstacle-like for ground path selection in the game: they
        remain technically reachable, but carry a huge cost so a safe route
        wins whenever one exists.  Flying units have no obstacle tiles.
        """
        tile = self.tiles[idx]
        if motion_mode == 0 and tile.is_hole:
            return 1000000.0
        return 1.0

    def _is_line_obstacle(self, idx, motion_mode):
        if idx < 0 or idx >= len(self.tiles):
            return True
        tile = self.tiles[idx]
        if tile.is_forbidden or not tile.passable(motion_mode):
            return True
        return motion_mode == 0 and tile.is_hole

    def _supercover_cells(self, start_idx, end_idx):
        """Cells checked by the game's conservative Bresenham smoothing.

        In addition to a supercover line, two close parallel rows/columns are
        fully checked when one axis differs by exactly one tile.  At an exact
        corner crossing both side cells are included as well.
        """
        r0, c0 = self.rc(start_idx)
        r1, c1 = self.rc(end_idx)
        dr, dc = abs(r1 - r0), abs(c1 - c0)
        if dr == 1 and dc > 0:
            return [self.idx(r, c)
                    for r in range(min(r0, r1), max(r0, r1) + 1)
                    for c in range(min(c0, c1), max(c0, c1) + 1)]
        if dc == 1 and dr > 0:
            return [self.idx(r, c)
                    for r in range(min(r0, r1), max(r0, r1) + 1)
                    for c in range(min(c0, c1), max(c0, c1) + 1)]

        x, y = c0, r0
        dx, dy = dc, dr
        sx = 1 if c1 > c0 else (-1 if c1 < c0 else 0)
        sy = 1 if r1 > r0 else (-1 if r1 < r0 else 0)
        cells = [start_idx]
        seen = {start_idx}

        def add(row, col):
            idx = self.idx(row, col)
            if idx not in seen:
                seen.add(idx)
                cells.append(idx)

        if dx >= dy:
            error = dx / 2.0
            for _ in range(dx):
                old_x, old_y = x, y
                x += sx
                error -= dy
                if error < 0:
                    y += sy
                    error += dx
                    # Whenever the shorter axis changes, validate the two
                    # side cells at that diagonal corner as well.
                    add(old_y, x)
                    add(y, old_x)
                add(y, x)
        else:
            error = dy / 2.0
            for _ in range(dy):
                old_x, old_y = x, y
                y += sy
                error -= dx
                if error < 0:
                    x += sx
                    error += dy
                    add(old_y, x)
                    add(y, old_x)
                add(y, x)
        return cells

    def _line_clear(self, start_idx, end_idx, motion_mode):
        return all(not self._is_line_obstacle(idx, motion_mode)
                   for idx in self._supercover_cells(start_idx, end_idx))

    def next_segment_contains(self, start_idx, next_idx, row, col):
        """Whether a tile lies on the current (possibly smoothed) segment.

        Blocking used to compare only against ``next_idx`` while next nodes
        were always adjacent.  Smoothed pointers can skip several tiles, so
        callers must consider every crossed tile along that segment.
        """
        target = self.idx(row, col)
        if target < 0 or start_idx < 0 or next_idx < 0:
            return False
        return target in self._supercover_cells(start_idx, next_idx)

    def _smooth_next_nodes(self, raw_next, motion_mode, allow_diagonal):
        """Make every nextNode point as far forward as safely possible."""
        out = list(raw_next)
        size = len(raw_next)
        for src in range(size):
            first = raw_next[src]
            if first < 0 or first == src:
                continue
            chain = []
            seen = {src}
            cur = first
            while 0 <= cur < size and cur not in seen:
                chain.append(cur)
                seen.add(cur)
                nxt = raw_next[cur]
                if nxt < 0 or nxt == cur:
                    break
                cur = nxt
            if not allow_diagonal:
                # The non-diagonal pass still collapses a straight run to
                # its next turn, without introducing a diagonal shortcut.
                sr, sc = self.rc(src)
                fr, fc = self.rc(first)
                step = (fr - sr, fc - sc)
                far = first
                prev = src
                for candidate in chain:
                    pr, pc = self.rc(prev)
                    cr, cc = self.rc(candidate)
                    if (cr - pr, cc - pc) != step:
                        break
                    far = candidate
                    prev = candidate
                out[src] = far
                continue
            # Candidates must remain nodes on the original cardinal shortest
            # path.  Only the farthest line-of-sight pointer is substituted;
            # raw SPFA distances are intentionally untouched.
            far = first
            for candidate in chain[1:]:
                if self._line_clear(src, candidate, motion_mode):
                    far = candidate
            out[src] = far
        return out

    # ---- flow field ----
    def build_flow_field(self, target_idx, motion_mode=0, allow_diagonal=True):
        """Four-way SPFA + Bresenham next-node smoothing.

        ``dist_map`` is the untouched cardinal distance.  Only ``next_map``
        changes when diagonal movement is allowed.
        """
        key = (motion_mode, allow_diagonal, target_idx)
        if key in self._next_map:
            return self._next_map[key], self._dist_map[key]
        raw_key = (motion_mode, target_idx)
        if raw_key in self._raw_next_map:
            raw_next = self._raw_next_map[raw_key]
            dist = self._raw_dist_map[raw_key]
        else:
            size = len(self.tiles)
            dist = [float("inf")] * size
            raw_next = [-1] * size
            dist[target_idx] = 0.0
            raw_next[target_idx] = target_idx
            q = deque([target_idx])
            inq = [False] * size
            inq[target_idx] = True
            while q:
                cur = q.popleft()
                inq[cur] = False
                dcur = dist[cur]
                for ni, _cost, _diag in self.neighbors(cur, motion_mode):
                    nd = dcur + self._path_cost(ni, motion_mode)
                    if nd < dist[ni] - 1e-9:
                        dist[ni] = nd
                        raw_next[ni] = cur
                        if not inq[ni]:
                            inq[ni] = True
                            q.append(ni)
            self._raw_next_map[raw_key] = raw_next
            self._raw_dist_map[raw_key] = dist
        nxt = self._smooth_next_nodes(raw_next, motion_mode,
                                      bool(allow_diagonal))
        self._next_map[key] = nxt
        self._dist_map[key] = dist
        return nxt, dist

    @staticmethod
    def route_motion_mode(route):
        raw = (route or {}).get("motionMode") or {}
        if isinstance(raw, dict):
            motion = raw.get("value")
        elif isinstance(raw, int):
            motion = raw
        else:
            motion = None
        return 0 if motion in (None, 2) else int(motion)

    @staticmethod
    def checkpoint_type(checkpoint):
        value = (checkpoint or {}).get("type")
        if isinstance(value, dict):
            value = value.get("value", 0)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def checkpoint_position(checkpoint):
        pos = (checkpoint or {}).get("position") or {}
        offset = (checkpoint or {}).get("reachOffset") or {}
        return {
            "row": float(pos.get("row", 0) or 0) +
                   float(offset.get("y", 0) or 0),
            "col": float(pos.get("col", 0) or 0) +
                   float(offset.get("x", 0) or 0),
        }

    @staticmethod
    def checkpoint_grid_position(checkpoint):
        """The path-field target tile ignores a checkpoint's reachOffset."""
        pos = (checkpoint or {}).get("position") or {}
        return {
            "row": float(pos.get("row", 0) or 0),
            "col": float(pos.get("col", 0) or 0),
        }

    def route_distance_to_final(self, route, checkpoint_index, row, col):
        """Remaining cardinal route distance across all later checkpoints.

        Each movement segment uses its own SPFA field.  APPEAR_AT_POS resets
        the segment origin, so tunnel travel contributes zero distance.
        """
        route = route or {}
        motion = self.route_motion_mode(route)
        allow_diag = bool(route.get("allowDiagonalMove", True))
        current = {"row": float(row), "col": float(col)}
        total = 0.0

        def add_segment(target, next_position=None):
            nonlocal current, total
            target_idx = self.idx(round(float(target.get("row", 0))),
                                  round(float(target.get("col", 0))))
            start_idx = self.idx(round(float(current.get("row", 0))),
                                 round(float(current.get("col", 0))))
            if target_idx < 0 or start_idx < 0:
                return False
            _nxt, dist = self.build_flow_field(
                target_idx, motion, allow_diag)
            value = dist[start_idx]
            if value == float("inf"):
                return False
            total += value
            current = dict(next_position or target)
            return True

        cps = route.get("checkpoints") or []
        for cp in cps[max(0, int(checkpoint_index or 0)):]:
            ctype = self.checkpoint_type(cp)
            if ctype in (0, 8, 10):       # MOVE/PATROL/MAP_OFFSET_MOVE
                if not add_segment(self.checkpoint_grid_position(cp),
                                   self.checkpoint_position(cp)):
                    return float("inf")
            elif ctype == 6:              # APPEAR_AT_POS: tunnel is free
                current = self.checkpoint_position(cp)
        if not add_segment(route.get("endPosition") or {}):
            return float("inf")
        return total

    def build_route_field(self, route, target_position=None):
        """Flow field for a route segment.

        ``target_position`` selects a MOVE/PATROL checkpoint.  Omitting it
        keeps the original final-exit behaviour.
        """
        motion = self.route_motion_mode(route)
        allow_diag = bool(route.get("allowDiagonalMove", True))
        end = target_position or route.get("endPosition") or {}
        end_idx = self.idx(round(float(end.get("row", 0) or 0)),
                           round(float(end.get("col", 0) or 0)))
        if end_idx < 0 or self.tiles[end_idx].is_forbidden:
            end_idx = self.end_tiles[0] if self.end_tiles else None
        if end_idx is None:
            return None, None, motion
        nxt, dist = self.build_flow_field(end_idx, motion, allow_diag)
        return nxt, dist, motion

    def path_distance(self, row, col, motion_mode=0, allow_diagonal=True,
                      target_idx=None):
        """distToFinal used by hate formula / UI."""
        if target_idx is None:
            target_idx = self.end_tiles[0] if self.end_tiles else self.idx(row, col)
        _n, dist = self.build_flow_field(target_idx, motion_mode, allow_diagonal)
        i = self.idx(row, col)
        return dist[i] if i >= 0 else float("inf")

    def route_path(self, route):
        """Polyline segments used by both movement and the web route layer.

        Only MOVE/PATROL/MAP_OFFSET_MOVE checkpoints create a flow field.
        APPEAR_AT_POS restarts the visible path at the appeared position, so
        the invisible tunnel distance is not drawn or counted.
        """
        route = route or {}
        current = route.get("startPosition") or {}
        segments = []

        def append_segment(target, kind, checkpoint_index=None,
                           next_position=None):
            nonlocal current
            nxt, dist, _motion = self.build_route_field(route, target)
            start_idx = self.idx(round(float(current.get("row", 0) or 0)),
                                 round(float(current.get("col", 0) or 0)))
            end_idx = self.idx(round(float(target.get("row", 0) or 0)),
                               round(float(target.get("col", 0) or 0)))
            points = []
            if nxt is not None and start_idx >= 0 and end_idx >= 0 and \
                    dist[start_idx] != float("inf"):
                cur = start_idx
                points.append(cur)
                seen = {cur}
                while cur != end_idx and len(points) <= len(self.tiles):
                    cur = nxt[cur]
                    if cur < 0 or cur in seen:
                        points = []
                        break
                    points.append(cur)
                    seen.add(cur)
            if points:
                segments.append({
                    "kind": kind,
                    "checkpointIndex": checkpoint_index,
                    "points": [{"row": self.rc(i)[0],
                                "col": self.rc(i)[1]} for i in points],
                    "distance": dist[start_idx],
                })
            current = dict(next_position or target)

        cps = route.get("checkpoints") or []
        for index, checkpoint in enumerate(cps):
            ctype = self.checkpoint_type(checkpoint)
            if ctype in (0, 8, 10):
                append_segment(self.checkpoint_grid_position(checkpoint),
                               "checkpoint", index,
                               self.checkpoint_position(checkpoint))
            elif ctype == 6:
                current = self.checkpoint_position(checkpoint)
        append_segment(route.get("endPosition") or {}, "end")
        return segments

    def buildable(self, row, col, buildable_type):
        t = self.tile(row, col)
        if t is None:
            return False
        if t.buildable_type is None:
            return False
        if t._buildable_override is not None:
            return bool(t._buildable_override & buildable_type)
        return bool(t.buildable_type & buildable_type)

    def rewrite_tile_buildable(self, row, col, mask):
        """Runtime buildable rewrite (RewriteTileOptionsInRange): replace
        the tile's buildable mask (0 = undeployable). Returns True when
        the tile exists and the value changed."""
        t = self.tile(row, col)
        if t is None:
            return False
        old = t.buildable_type
        new = t.set_buildable_override(mask)
        return new != old

    def restore_tile_buildable(self, row, col):
        """Restore the tile's base buildableType (ON_BUFF_FINISH of the
        rewrite templates). Returns True when an override was active."""
        t = self.tile(row, col)
        if t is None:
            return False
        if t._buildable_override is None:
            return False
        t.set_buildable_override(None)
        return True

    def rewrite_tile_passable(self, row, col, passable_mask):
        """Runtime tile rewrite (RewriteTileOptions): override the passable
        mask and drop every cached flow field so enemies re-route."""
        t = self.tile(row, col)
        if t is None:
            return False
        t.set_passable_override(passable_mask)
        self._raw_next_map.clear()
        self._raw_dist_map.clear()
        self._next_map.clear()
        self._dist_map.clear()
        self._revision += 1
        return True

    def restore_tile_passable(self, row, col):
        """Restore the tile's original passable mask (clear override)."""
        t = self.tile(row, col)
        if t is None:
            return False
        if t._passable_override is None:
            return False
        t.set_passable_override(None)
        self._raw_next_map.clear()
        self._raw_dist_map.clear()
        self._next_map.clear()
        self._dist_map.clear()
        self._revision += 1
        return True

    def to_dict(self):
        return {
            "rows": self.rows,
            "cols": self.cols,
            "tiles": [t.to_dict() for t in self.tiles],
            "endTiles": [self.rc(i) for i in self.end_tiles],
        }


def _dir4(dr, dc):
    """Map (dr,dc) to directional index for blockEdges (0=right,1=down,
    2=left,3=up)."""
    if dr == 0 and dc == 1:
        return 0
    if dr == 1 and dc == 0:
        return 1
    if dr == 0 and dc == -1:
        return 2
    if dr == -1 and dc == 0:
        return 3
    return -1
