"""Act31Side pollute-area mechanic (13-04 hard boss fight, dhnzzh).

The boss spreads pollution on tiles; clean-water skills purify areas.  The
emulator tracks a per-tile pollute map, resolves the ``_addPolluteV`` value
from the source unit's blackboard when the field is 0, and exposes the
area gates / assignments.  Water-area connectivity and flow pumping are
approximated (【推】): the polluted tiles themselves act as the water area.
"""


_EXCLUDED_TILES = frozenset(
    {"tile_forbidden", "tile_wall", "tile_start", "tile_end"})


class Act31PolluteManager:
    def __init__(self, battle):
        self.battle = battle
        self.pollute = {}           # (r,c) -> value
        self.water_tiles = set()    # tiles in a water area
        self.rebuild_count = 0
        self.pump_count = 0

    # ---- value helpers ------------------------------------------------
    @staticmethod
    def pollute_value(source, node_value):
        """The node's _addPolluteV is often 0 in data; the real amount
        comes from the source unit's blackboard (value / value_eff)."""
        if node_value:
            return int(node_value)
        bb = getattr(source, "blackboard", None) or {}
        if isinstance(bb, dict):
            v = bb.get("value")
            if v in (None, ""):
                v = bb.get("value_eff")
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
        return 100

    # ---- mutations ----------------------------------------------------
    def _valid_tile(self, r, c, need_check_tile):
        if self.battle.map.idx(r, c) < 0:
            return False
        if not need_check_tile:
            return True
        t = self.battle.map.tile(r, c)
        return not (t is None or t.tile_key in _EXCLUDED_TILES)

    def add_area_pollute(self, r, c, value, radius=1.0,
                         need_check_tile=True):
        n = 0
        rad = max(0, int(radius or 0))
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                rr, cc = r + dr, c + dc
                if not self._valid_tile(rr, cc, need_check_tile):
                    continue
                self.pollute[(rr, cc)] = max(
                    0, self.pollute.get((rr, cc), 0) + value)
                n += 1
        if n:
            self._emit("act31_pollute_add",
                       {"row": r, "col": c, "value": value, "tiles": n})
        return n > 0

    def _area_at(self, r, c):
        """4-connected polluted tiles reachable from (r,c)."""
        if (r, c) not in self.pollute:
            return []
        seen, stack = {(r, c)}, [(r, c)]
        while stack:
            rr, cc = stack.pop()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (rr + dr, cc + dc)
                if nb in self.pollute and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        return list(seen)

    def purify_area_pollute(self, r, c, value):
        area = self._area_at(r, c)
        if not area:
            return False
        for rr, cc in area:
            nv = self.pollute[(rr, cc)] - value
            if nv <= 0:
                del self.pollute[(rr, cc)]
            else:
                self.pollute[(rr, cc)] = nv
        self._emit("act31_pollute_purify",
                   {"row": r, "col": c, "value": value,
                    "tiles": len(area)})
        return True

    def death_pollute_tile(self, r, c, radius=1.0, value=100):
        return self.add_area_pollute(r, c, value, radius,
                                     need_check_tile=True)

    def rebuild_areas(self):
        """Recompute water tiles from polluted tiles (【推】: the polluted
        area is the water area in the 13-04 fight)."""
        self.water_tiles = set(self.pollute.keys())
        self.rebuild_count += 1
        self._emit("act31_rebuild_areas", {"tiles": len(self.water_tiles)})
        return True

    def pump_flow(self, r, c, range_id=""):
        self.pump_count += 1
        self._emit("act31_pump_flow", {"row": r, "col": c,
                                       "rangeId": range_id})
        return True

    # ---- gates --------------------------------------------------------
    def check_in_pollute_area(self, r, c):
        return (r, c) in self.pollute

    def check_tile_in_water_area(self, r, c):
        return (r, c) in self.water_tiles or (r, c) in self.pollute

    def check_root_tile_pollute_value(self, r, c, cond, value,
                                      need_area_pv=False):
        v = self.pollute.get((r, c), 0)
        if need_area_pv:
            area = self._area_at(r, c)
            if area:
                v = max(self.pollute.get(p, 0) for p in area)
        c = str(cond).upper()
        if c == "GE":
            return v >= value
        if c == "GT":
            return v > value
        if c == "LE":
            return v <= value
        if c == "LT":
            return v < value
        if c == "EQ":
            return v == value
        return v >= value

    # ---- snapshot -----------------------------------------------------
    def to_dict(self):
        return {
            "pollutedTiles": len(self.pollute),
            "waterTiles": len(self.water_tiles),
            "rebuilds": self.rebuild_count,
            "pumps": self.pump_count,
            "pollute": {f"{r},{c}": v
                        for (r, c), v in sorted(self.pollute.items())},
        }

    def _emit(self, event, payload):
        try:
            self.battle.emit(self.battle.tick, event, payload)
        except Exception:
            pass
