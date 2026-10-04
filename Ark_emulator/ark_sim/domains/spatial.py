"""Deterministic grid topology and geometry, independent of movement rates."""
import math
import heapq
from collections import deque
from collections.abc import Mapping

from ark_sim.contracts import thaw


class UnreachablePathError(ValueError):
    pass


def project_cell(position):
    """Standard model cell projection: exact half ties toward positive infinity.

    This is a shared geometry profile, not a claim about native comparators.
    It projects finite continuous coordinates without imposing map bounds.
    """
    if not isinstance(position, Mapping) or not {"row", "col"}.issubset(position):
        raise ValueError("position needs row and col")
    values = []
    for coordinate in ("row", "col"):
        value = position[coordinate]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("position coordinates must be finite numbers")
        values.append(math.floor(value + 0.5))
    return tuple(values)


def route_motion_mode(route):
    """Decode the declared locomotion mode without guessing unknown enums."""
    value = (route or {}).get("motionMode")
    names = {"WALK": 0, "FLY": 1}
    if value is None:
        return 0  # Backward-compatible normalized ground fixtures.
    if isinstance(value, Mapping):
        if set(value)-{"name", "value"}:
            raise ValueError("Unknown route motion fields")
        name, number = value.get("name"), value.get("value")
        if name is not None and name not in names:
            raise ValueError(f"Unsupported route motion name {name!r}")
        if number is None and name in names:
            return names[name]
        if type(number) is not int or number not in (0, 1):
            raise ValueError(f"Unsupported route motion value {number!r}")
        if name is not None and names[name] != number:
            raise ValueError("Route motion name/value mismatch")
        return number
    if isinstance(value, str):
        if value not in names:
            raise ValueError(f"Unsupported route motion name {value!r}")
        return names[value]
    if type(value) is not int or value not in (0, 1):
        raise ValueError(f"Unsupported route motion value {value!r}")
    return value


class GridTopology:
    """Row-major tiles and safe four-neighbour shortest paths.

    Tile centres have integer row/col coordinates. Returned paths exclude the
    origin and include the destination. No diagonal corner cutting is applied.
    """
    _NEIGHBOURS = ((-1, 0), (0, -1), (0, 1), (1, 0))

    def __init__(self, map_definition):
        if not isinstance(map_definition, Mapping):
            raise ValueError("map definition must be an object")
        self.tile_reader = None
        self.tile_mechanics = thaw(map_definition.get("tile_mechanics", {}))
        from .tile_mechanics import validate_cell_profiles
        self.tile_cell_mechanics = thaw(validate_cell_profiles(map_definition))
        self.rows, self.cols = map_definition.get("rows"), map_definition.get("cols")
        for field, value in (("rows", self.rows), ("cols", self.cols)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"map {field} must be a positive integer")
        tiles = map_definition.get("tiles")
        if tiles is None:
            self._tiles = [{"tileKey": "tile_floor", "passableMask": 1, "buildableType": 1}
                           for _ in range(self.rows * self.cols)]
        else:
            if not isinstance(tiles, (list, tuple)) or len(tiles) != self.rows * self.cols:
                raise ValueError("map tiles must contain exactly rows * cols row-major entries")
            if any(not isinstance(tile, Mapping) for tile in tiles):
                raise ValueError("map tiles must be objects")
            self._tiles = thaw(tiles)
        from .tile_mechanics import validate_profiles
        validate_profiles(self.tile_mechanics)
        for tile in self._tiles:
            profile=self.tile_mechanics.get(tile.get('tileKey'),{})
            if profile.get('type')=='declared_static_tile':
                for field,expected in profile['expected_options'].items():
                    if type(tile.get(field)) is not type(expected) or tile.get(field)!=expected:raise ValueError('static tile runtime source option differs')
                for field in ('blackboard','effects'):
                    expected=profile['expected_'+field]
                    if type(tile.get(field)) is not type(expected) or tile.get(field)!=expected:raise ValueError('static tile runtime source data differs')
            mask = tile.get("passableMask", 1)
            if mask is not None and (type(mask) is not int or mask < 0):
                raise ValueError("tile passableMask must be a nonnegative integer")

    def inside(self, row, col):
        return (type(row) is int and type(col) is int and
                0 <= row < self.rows and 0 <= col < self.cols)

    def tile(self, row, col):
        if not self.inside(row, col):
            raise ValueError(f"tile outside map: ({row}, {col})")
        return self.tile_reader(row, col) if self.tile_reader else thaw(self._tiles[row * self.cols + col])

    def passable(self, row, col):
        if not self.inside(row, col):
            return False
        tile = self.tile(row, col)
        contact=self.tile_mechanics.get(tile.get("tileKey"),{})
        if contact.get("type")=="contact_lifecycle":return contact["normal_path_passable"]
        if "groundPassable" in tile:
            return tile["groundPassable"]
        key = tile.get("tileKey", "tile_floor")
        if key in {"tile_wall", "tile_forbidden", "tile_flystart"}:
            return False
        if key in {"tile_start", "tile_end"}:
            return True
        return bool((tile.get("passableMask", 1) or 0) & 1)

    def appearance_passable(self,row,col):
        if not self.inside(row,col):return False
        profile=self.tile_mechanics.get(self.tile(row,col).get("tileKey"),{})
        return profile["appearance_contact_passable"] if profile.get("type")=="contact_lifecycle" else self.passable(row,col)

    def _cell(self, position):
        cell = project_cell(position)
        if not self.inside(*cell):
            raise ValueError(f"position outside map: {dict(position)}")
        return cell

    def clip_segment(self, origin, destination, motion_mode=0, forced=False):
        """Point-body grid collision at exact cell boundaries, no tunneling."""
        row, col = self._cell(origin)
        dr, dc = destination["row"]-origin["row"], destination["col"]-origin["col"]
        if not dr and not dc:
            return dict(origin), False
        step_r, step_c = (1 if dr > 0 else -1), (1 if dc > 0 else -1)
        next_r = ((row + .5*step_r)-origin["row"])/dr if dr else math.inf
        next_c = ((col + .5*step_c)-origin["col"])/dc if dc else math.inf
        inc_r, inc_c = abs(1/dr) if dr else math.inf, abs(1/dc) if dc else math.inf
        def valid(r, c):
            if not self.inside(r,c):return False
            profile=self.tile_mechanics.get(self.tile(r,c).get("tileKey"),{})
            contact=forced and profile.get("type")=="contact_lifecycle" and profile["forced_contact_passable"]
            return motion_mode == 1 or contact or self.passable(r,c)
        for _ in range(self.rows+self.cols+4):
            at = min(next_r, next_c)
            if at > 1:
                return dict(destination), False
            cross_r, cross_c = next_r <= next_c, next_c <= next_r
            rr, cc = row+step_r if cross_r else row, col+step_c if cross_c else col
            blocked = not valid(rr, cc)
            if cross_r and cross_c:
                blocked = blocked or not valid(rr, col) or not valid(row, cc)
            if blocked:
                point = {"row": origin["row"]+dr*max(0, at), "col": origin["col"]+dc*max(0, at)}
                for axis in ("row", "col"):
                    if point[axis] != origin[axis]:
                        point[axis] = math.nextafter(point[axis], origin[axis])
                # Half-up adds .5 before floor: one nextafter may round back
                # onto the forbidden boundary. Stabilize only this opted-in
                # contact map, preserving the unconfigured legacy path.
                if any(p.get("type")=="contact_lifecycle" for p in self.tile_mechanics.values()):
                    for _back in range(8):
                        if project_cell(point)==(row,col):break
                        for axis in ("row","col"):
                            if point[axis]!=origin[axis]:point[axis]=math.nextafter(point[axis],origin[axis])
                    if project_cell(point)!=(row,col):raise ValueError("clipped point must remain in preceding cell")
                return point, True
            row, col = rr, cc
            if cross_r:
                next_r += inc_r
            if cross_c:
                next_c += inc_c
        raise ValueError("grid segment traversal exceeded map boundary")

    def path(self, origin, destination, motion_mode=0, allow_diagonal=False, corner_cut=False):
        start, end = self._cell(origin), self._cell(destination)
        mode = route_motion_mode({"motionMode": motion_mode})
        target = {"row": destination["row"], "col": destination["col"]}
        if mode == 1:
            # One declared segment. Checkpoint sequencing stays in MovementSystem;
            # no wall detour or direct shortcut to a later checkpoint is added.
            return [] if dict(origin) == target else [target]
        if not self.passable(*start) or not self.passable(*end):
            raise UnreachablePathError(f"Route endpoint is not ground-passable: {start} -> {end}")
        if start == end:
            return [] if origin["row"] == target["row"] and origin["col"] == target["col"] else [target]
        if allow_diagonal or any(self.tile(r, c).get("movementCost", 1) != 1 for r in range(self.rows) for c in range(self.cols)):
            return self._diagonal_path(start, end, target, corner_cut, allow_diagonal)
        queue = deque([start])
        previous = {start: None}
        while queue and end not in previous:
            row, col = queue.popleft()
            for dr, dc in self._NEIGHBOURS:
                neighbour = (row + dr, col + dc)
                if neighbour not in previous and self.passable(*neighbour):
                    previous[neighbour] = (row, col)
                    queue.append(neighbour)
        if end not in previous:
            raise UnreachablePathError(f"No ground route: {start} -> {end}")
        route = []
        current = end
        while current != start:
            route.append({"row": current[0], "col": current[1]})
            current = previous[current]
        route.reverse()
        route[-1] = target
        return route

    def _diagonal_path(self, start, end, target, corner_cut, allow_diagonal=True):
        queue, distances, previous = [(0, *start)], {start: 0}, {start: None}
        neighbours = (*self._NEIGHBOURS, (-1, -1), (-1, 1), (1, -1), (1, 1)) if allow_diagonal else self._NEIGHBOURS
        while queue:
            cost, row, col = heapq.heappop(queue)
            if cost != distances[(row, col)]:
                continue
            if (row, col) == end:
                break
            for dr, dc in neighbours:
                neighbour = (row+dr, col+dc)
                if not self.passable(*neighbour):
                    continue
                if dr and dc and not corner_cut and (
                        not self.passable(row+dr, col) or not self.passable(row, col+dc)):
                    continue
                candidate = cost+(math.sqrt(2) if dr and dc else 1)*self.tile(*neighbour).get("movementCost", 1)
                if candidate < distances.get(neighbour, math.inf):
                    distances[neighbour], previous[neighbour] = candidate, (row, col)
                    heapq.heappush(queue, (candidate, *neighbour))
        if end not in previous:
            raise UnreachablePathError(f"No diagonal ground route: {start} -> {end}")
        route, current = [], end
        while current != start:
            route.append({"row": current[0], "col": current[1]})
            current = previous[current]
        route.reverse()
        route[-1] = target
        return route
