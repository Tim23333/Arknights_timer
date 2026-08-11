"""Act35SideBattleManager equivalent (dump.cs:10261) - the env_017_act35side
gem mechanic (Clear / Polluted gems) reused by the mainline 15-18 boss fight.

The gems are stationary enemies (enemy_10009_sggem) occupying tiles; the
manager tracks the gem-type map, answers tile/count queries and performs
line eliminations.  The full match-3 area-elimination (connected sub-areas,
damage transfer between linked gems) is documented as 【推】-lite: the
summon / gate / count / line-eliminate core is implemented; deep area
re-evaluation stays on the gem templates' buff handlers.
"""

from .consts import EnemyState


GEMS_ENEMY_ID = "enemy_10009_sggem"
LINK_TRAP_ID = "trap_182_sglink"

# GemsType (dump.cs:394988): Null=0 Clear=1 Polluted=2 -> type buff
TYPE_BUFF = {
    "Clear": "enemy_sggem_t[clear]",
    "Polluted": "enemy_sggem_t[polluted]",
}

# tiles on which gems can never be summoned (Act35SideBattleManager
# ExcludedTileKey + map borders)
EXCLUDED_TILE_KEYS = frozenset(
    {"tile_forbidden", "tile_start", "tile_end", "tile_wall"})

_DIRS = {
    "UP": (-1, 0),
    "DOWN": (1, 0),
    "LEFT": (0, -1),
    "RIGHT": (0, 1),
}


class Act35GemsManager:
    """Per-battle gem map + summon / query / eliminate API."""

    def __init__(self, battle):
        self.battle = battle
        self.gems = {}          # (r,c) -> {"type", "is_link", "enemy"}
        self.summoned_count = 0
        self.eliminated_count = 0

    # ---- queries -----------------------------------------------------
    def check_on_gems_tile(self, row, col, exclude_link_gems=False):
        g = self.gems.get((int(row), int(col)))
        if g is None:
            return False
        if exclude_link_gems and g.get("is_link"):
            return False
        return True

    def gems_count(self, exclude_link_gems=False):
        if not exclude_link_gems:
            return len(self.gems)
        return sum(1 for g in self.gems.values()
                   if not g.get("is_link"))

    def check_not_on_excluded_tile(self, row, col):
        try:
            t = self.battle.map.tile(int(row), int(col))
            return not (t is not None and
                        (t.tile_key in EXCLUDED_TILE_KEYS or
                         not t.passable(0)))
        except Exception:
            return True

    # ---- summon ------------------------------------------------------
    def _valid_tile(self, r, c):
        m = self.battle.map
        if m.idx(r, c) < 0:
            return False
        t = m.tile(r, c)
        if t is None or t.tile_key in EXCLUDED_TILE_KEYS:
            return False
        if (r, c) in self.gems:
            return False
        for e in self.battle.get_enemies():
            if not getattr(e, "dead", False) and \
                    (int(e.row), int(e.col)) == (r, c):
                return False
        return True

    def summon_gem(self, row, col, gems_type="Polluted"):
        r, c = int(row), int(col)
        if not self._valid_tile(r, c):
            return False
        try:
            e = self.battle.spawn_enemy_directive(
                GEMS_ENEMY_ID, r, c, route_index=0)
        except Exception:
            return False
        try:
            e.move_speed = 0.0     # gems are stationary blockers
            e.state = EnemyState.MOVE
        except Exception:
            pass
        key = TYPE_BUFF.get(gems_type) or TYPE_BUFF["Polluted"]
        try:
            from .buff_templates import materialise_buff
            entry = materialise_buff(
                self.battle, e, {"buffKey": key, "templateKey": key}, {}, e)
            if entry:
                self.battle.add_buff(e, entry)
        except Exception:
            pass
        self.gems[(r, c)] = {"type": gems_type, "is_link": False, "enemy": e}
        self.summoned_count += 1
        self._emit("act35_gem_summon",
                   {"row": r, "col": c, "type": gems_type,
                    "instId": getattr(e, "inst_id", None)})
        return True

    def summon_gems_in_four_directions(self, row, col, gems_type="Polluted"):
        n = 0
        for dr, dc in _DIRS.values():
            if self.summon_gem(row + dr, col + dc, gems_type):
                n += 1
        return n > 0

    def summon_gems_in_range(self, row, col, gems_type="Polluted",
                             range_id="", is_circle=False, radius=0.0,
                             direction="UP"):
        cells = []
        if is_circle or not range_id:
            rad = max(1, int(radius or 1))
            for dr in range(-rad, rad + 1):
                for dc in range(-rad, rad + 1):
                    cells.append((dr, dc))
        else:
            try:
                from .battle import _load_range_table
                rt = _load_range_table()
                shape = (rt.get(range_id) or {}).get("grids") or []
                cells = [(int(g.get("row", 0)), int(g.get("col", 0)))
                         for g in shape]
            except Exception:
                cells = [(0, 0)]
        n = 0
        for dr, dc in cells:
            if self.summon_gem(row + dr, col + dc, gems_type):
                n += 1
        return n > 0

    def summon_link_gem(self, row, col):
        """Mark the tile as a link gem (LINK_TRAP_ID marker in the game;
        the map entry is what gates / counts / eliminations read)."""
        r, c = int(row), int(col)
        if (r, c) in self.gems or self.battle.map.idx(r, c) < 0:
            return False
        self.gems[(r, c)] = {"type": "Link", "is_link": True, "enemy": None}
        self.summoned_count += 1
        return True

    # ---- elimination -------------------------------------------------
    def eliminate_gems(self, row, col, direction="UP"):
        """EliminateGemsByPositionAndDirection: remove gems on the target
        tile and every consecutive gem along the direction line."""
        m = self.battle.map
        dr, dc = _DIRS.get(direction, _DIRS["UP"])
        r, c = int(row), int(col)
        removed = 0
        for _ in range(max(m.rows, m.cols) + 1):
            if m.idx(r, c) < 0:
                break
            g = self.gems.pop((r, c), None)
            if g is None:
                r += dr
                c += dc
                continue
            e = g.get("enemy")
            if e is not None and not getattr(e, "dead", False):
                try:
                    from .consts import DamageType
                    self.battle.apply_damage(e, 10 ** 9, DamageType.TRUE,
                                             source=None)
                except Exception:
                    pass
            self.eliminated_count += 1
            removed += 1
            r += dr
            c += dc
        if removed:
            self._emit("act35_gems_eliminated",
                       {"row": int(row), "col": int(col),
                        "direction": direction, "count": removed})
        return removed > 0

    # ---- per-tick ----------------------------------------------------
    def on_tick(self):
        """Drop entries whose gem enemy was killed (attacked by players)."""
        dead = []
        for (r, c), g in self.gems.items():
            e = g.get("enemy")
            if e is not None and (getattr(e, "dead", False) or
                                  e not in self.battle.enemies):
                dead.append((r, c))
        for r, c in dead:
            del self.gems[(r, c)]
            self.eliminated_count += 1

    # ---- snapshot ----------------------------------------------------
    def to_dict(self):
        return {
            "count": len(self.gems),
            "summoned": self.summoned_count,
            "eliminated": self.eliminated_count,
            "gems": [{
                "row": r, "col": c, "type": g["type"],
                "isLink": g.get("is_link", False),
                "instId": getattr(g.get("enemy"), "inst_id", None),
            } for (r, c), g in sorted(self.gems.items())],
        }

    def _emit(self, event, payload):
        try:
            self.battle.emit(self.battle.tick, event, payload)
        except Exception:
            pass
