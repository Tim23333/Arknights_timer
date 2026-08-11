"""Map model and pathfinding for the battle simulation.

Implements the game's flow-field approach (see docs 05_movement_routes.md):
for each route we run SPFA backward from the end tile to produce a
``nextNode``/``distToFinal`` field for every tile, so an enemy only has to
read its current tile's pointer each move tick. Movement honours
``passableMask`` (MotionMask), per-direction ``blockEdges`` and
``allowDiagonalMove``.

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
        self._next_map = {}   # (motion_mode, allow_diag, target_idx) -> list[int]
        self._dist_map = {}   # same key -> list[float]
        self._edge_blocked = {}  # (src_idx, dir4) -> bool (from blockEdges)

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

    def neighbors(self, idx, motion_mode, allow_diagonal):
        """Yield (neighbor_idx, step_cost, is_diag)."""
        r, c = self.rc(idx)
        # 4-directional moves
        dirs = ((0, 1, 1.0), (1, 0, 1.0), (0, -1, 1.0), (-1, 0, 1.0))
        if allow_diagonal:
            diags = ((1, 1, 1.41421356), (1, -1, 1.41421356),
                     (-1, 1, 1.41421356), (-1, -1, 1.41421356))
            dirs = dirs + diags
        for dr, dc, cost in dirs:
            nr, nc = r + dr, c + dc
            ni = self.idx(nr, nc)
            if ni < 0:
                continue
            t = self.tiles[ni]
            if not t.passable(motion_mode) or t.is_forbidden:
                continue
            if dr and dc:
                # diagonal requires both orthogonal neighbours passable
                a = self.idx(r, c + dc)
                b = self.idx(r + dr, c)
                if a < 0 or b < 0:
                    continue
                if not self.tiles[a].passable(motion_mode) or \
                   not self.tiles[b].passable(motion_mode):
                    continue
            if self._edge_blocked.get((idx, _dir4(dr, dc))):
                continue
            yield ni, cost, bool(dr and dc)

    # ---- flow field ----
    def build_flow_field(self, target_idx, motion_mode=0, allow_diagonal=True):
        """SPFA/BFS from target backwards; returns (next_map, dist_map)."""
        key = (motion_mode, allow_diagonal, target_idx)
        if key in self._next_map:
            return self._next_map[key], self._dist_map[key]
        size = len(self.tiles)
        dist = [float("inf")] * size
        nxt = [-1] * size
        dist[target_idx] = 0.0
        nxt[target_idx] = target_idx
        q = deque([target_idx])
        inq = [False] * size
        inq[target_idx] = True
        while q:
            cur = q.popleft()
            inq[cur] = False
            dcur = dist[cur]
            for ni, cost, _diag in self.neighbors(cur, motion_mode, allow_diagonal):
                nd = dcur + cost
                if nd < dist[ni] - 1e-9:
                    dist[ni] = nd
                    nxt[ni] = cur
                    if not inq[ni]:
                        inq[ni] = True
                        q.append(ni)
        self._next_map[key] = nxt
        self._dist_map[key] = dist
        return nxt, dist

    def build_route_field(self, route):
        """Flow field for a route; targets its end tile (fallback: any end)."""
        _mm = route.get("motionMode") or {}
        if isinstance(_mm, dict):
            motion = _mm.get("value")
        elif isinstance(_mm, int):
            motion = _mm
        else:
            motion = None
        motion = 0 if motion in (None, 2) else motion  # E_NUM=2 -> walk default
        allow_diag = bool(route.get("allowDiagonalMove", True))
        end = route.get("endPosition") or {}
        end_idx = self.idx(end.get("row", 0), end.get("col", 0))
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
        self._next_map.clear()
        self._dist_map.clear()
        return True

    def restore_tile_passable(self, row, col):
        """Restore the tile's original passable mask (clear override)."""
        t = self.tile(row, col)
        if t is None:
            return False
        if t._passable_override is None:
            return False
        t.set_passable_override(None)
        self._next_map.clear()
        self._dist_map.clear()
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
