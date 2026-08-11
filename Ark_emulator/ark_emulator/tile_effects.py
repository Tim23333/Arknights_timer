"""Tile (field) effects - terrain behaviour on units standing on a tile.

Data: ``data_tile_defs.json`` extracted from the game's ``[uc]tiles.ab``
(111 tile prefabs). Each tile may:
  - grant buffs (tile_healing, tile_defup, tile_sleep_road, ...)
  - deal damage over time (tile_volcano, tile_toxic, tile_creep, ...)
  - change passability / block movement (tile_hole, tile_quicksand, ...)

The buff/damage values are read from the tile's blackboard (loaded per
level); defaults come from the prefab definition.
"""

import io
import json
import os
import re

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "data_tile_defs.json")
_cache = None


def load_tile_defs():
    global _cache
    if _cache is None:
        with io.open(_DATA, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


# script pathID -> behaviour kind (from dump.cs Tile class families)
SCRIPT_KIND = {
    8764313853837755128: "buff_tile",        # DynamicBuffTile (heal/def/sleep/grass)
    5974031364498975591: "dot_tile",         # ToxicTile family (originum/poison dot)
    1619364305013091376: "dot_tile",         # CreepTile (creep dot)
    -3608587646578225672: "volcano_tile",    # VolcanoTile family (eruption dot)
    -3248894570733953654: "ice_tile",        # IceCornerTile family
    541498498131890977: "quicksand_tile",    # DynamicBuffQuickSandTile
    -6207797234824094909: "reed_tile",       # ReedTile (igniteable)
    -2826163073248832506: "hole_tile",       # HoleTile
    -4476749712907006088: "ice_tile",        # IceStrTile
    -7560412107378972631: "deepsea_tile",    # DeepSeaTile
    -280084592620942506: "infection_tile",   # InfectionTile
    -6182944975699274800: "yinyang_tile",    # YinYangTile
    135137571731858317: "gravity_tile",      # GravityButtonTile
    294045865278070107: "wood_tile",         # WoodTile
    5179941577750269553: "mire_tile",        # MireTile
}


def tile_kind(tile_key, defs=None):
    """Behaviour kind for a tile key ('' = plain terrain)."""
    defs = defs or load_tile_defs()
    t = defs.get(tile_key)
    if not t:
        return ""
    return SCRIPT_KIND.get(t.get("scriptPathId"), "buff_tile"
                           if t.get("buffs") or t.get("dynamicBuffs") else "")


def tile_blackboard_defaults(tile_key, defs=None):
    """Default blackboard values from the tile prefab definition."""
    defs = defs or load_tile_defs()
    t = defs.get(tile_key) or {}
    bb = {}
    for b in (t.get("buffs") or []):
        for mod in (b.get("attributes") or {}).get("attributeModifiers") or []:
            if mod.get("loadFromBlackboard"):
                key = _attr_key(mod.get("attributeType"))
                if key:
                    bb[key] = mod.get("value")
    return bb


_ATTR_NAMES = {1: "atk", 2: "def", 3: "maxHp", 19: "hpRecoveryPerSec",
               33: "attackSpeed", 34: "moveSpeed"}


def _attr_key(attr_type):
    return _ATTR_NAMES.get(attr_type)


def tile_buff_keys(tile_key, defs=None):
    """All buff keys a tile applies across every dynamic mode."""
    defs = defs or load_tile_defs()
    t = defs.get(tile_key) or {}
    keys = []
    for b in (t.get("buffs") or []):
        if isinstance(b, dict) and b.get("buffKey"):
            keys.append(b["buffKey"])
    for db in (t.get("dynamicBuffs") or []):
        for b in (db.get("buffs") or []):
            if isinstance(b, dict) and b.get("buffKey"):
                keys.append(b["buffKey"])
    return keys


class TileEffectSystem:
    """Applies tile effects each tick to units standing on affected tiles."""

    def __init__(self, battle):
        self.battle = battle
        self.defs = load_tile_defs()
        self._active_buffs = {}   # (unit_id, tile_key) -> buff list

    def tick(self):
        """Per-tick terrain effect pass (called by BattleController).

        Tile effects respect the prefab's targetSide (SideType enum:
        1=ALLY 2=ENEMY 3=BOTH 7=ALL); a buff/damage tile only affects the
        unit sides it targets (healing/grass/def tiles are ally-only,
        quicksand/deep-sea/wood are enemy-only)."""
        battle = self.battle
        enemy_ids = {id(u) for u in battle.get_enemies()}
        for unit in list(battle.get_enemies()) + list(battle.get_operators()) \
                + list(battle.get_tokens()):
            if unit.dead:
                continue
            tile = battle.get_tile(unit.row, unit.col)
            if tile is None:
                continue
            t = self.defs.get(tile.tile_key) or {}
            target_side = t.get("targetSide")
            if target_side not in (None, 0, 3, 7):
                side = 2 if id(unit) in enemy_ids else 1
                if target_side != side:
                    continue
            kind = tile_kind(tile.tile_key, self.defs)
            if kind == "dot_tile":
                self._apply_dot(unit, tile)
            elif kind == "volcano_tile":
                self._apply_volcano(unit, tile)
            elif kind == "buff_tile":
                self._apply_buff(unit, tile)
            elif kind == "infection_tile":
                self._apply_infection(unit, tile)
            elif kind == "hole_tile":
                self._apply_hole(unit, tile)
            elif kind in ("mire_tile", "ice_tile", "quicksand_tile",
                          "reed_tile", "deepsea_tile", "yinyang_tile",
                          "wood_tile"):
                # template-driven terrain buffs (slow/cold/flammable/
                # under-sea/yin-yang) - applied through the buff engine
                self._apply_tile_template_buffs(unit, tile)
            # conveyor: ? tile blackboard ? conveyor_speed ??
            self._apply_conveyor(unit, tile)
            # gravity button: ??/??????????? shake buff?
            if kind == "gravity_tile":
                self._apply_gravity_button(unit, tile)

    def _tile_actions(self, tile):
        """Parse prefab _actions.SerializedState into a list of node dicts."""
        t = self.defs.get(tile.tile_key) or {}
        raw = (t.get("actions") or {}).get("SerializedState")
        if not raw or raw == "null":
            return []
        try:
            import json as _json
            return _json.loads(raw)
        except Exception:
            return []

    def _apply_dot(self, unit, tile):
        """Toxic/originum tiles: periodic true/magical damage."""
        battle = self.battle
        bb = battle.tile_blackboard(unit.row, unit.col)
        actions = self._tile_actions(tile)
        dmg_type = 2  # PURE default
        dmg = float(bb.get("damage") or bb.get("atk") or 100.0)
        interval = float(bb.get("interval") or 1.0)
        for a in actions:
            if "NoSourceDamage" in str(a.get("$type", "")):
                dmg_type = {"PURE": 2, "PHYSICAL": 0,
                            "MAGICAL": 1}.get(a.get("_damageType"), 2)
        if battle.tick % max(1, int(round(interval * 30))) != 0:
            return
        battle.apply_damage(unit, dmg, dmg_type, source=None)

    def _apply_volcano(self, unit, tile):
        battle = self.battle
        bb = battle.tile_blackboard(unit.row, unit.col)
        actions = self._tile_actions(tile)
        dmg_type = 2
        for a in actions:
            if "NoSourceDamage" in str(a.get("$type", "")):
                dmg_type = {"PURE": 2, "PHYSICAL": 0,
                            "MAGICAL": 1}.get(a.get("_damageType"), 2)
        dmg = float(bb.get("damage") or 400.0)
        interval = float(bb.get("interval") or 1.0)
        if battle.tick % max(1, int(round(interval * 30))) != 0:
            return
        battle.apply_damage(unit, dmg, dmg_type, source=None)

    def _apply_buff(self, unit, tile):
        """Terrain buffs (heal/def/sleep): apply/refresh a standing buff.

        The modifier value is loaded from the tile blackboard
        (loadFromBlackboard=true in the prefab); the real number comes from
        the per-tile blackboard (level params / map_tile_blackb runes), so
        it is read first and falls back to the prefab default."""
        battle = self.battle
        t = self.defs.get(tile.tile_key) or {}
        bb = battle.tile_blackboard(unit.row, unit.col)
        buffs = t.get("buffs") or []
        for b in buffs:
            key = b.get("buffKey")
            if not key:
                continue
            mods = (b.get("attributes") or {}).get("attributeModifiers") or []
            for mod in mods:
                stat = _attr_key(mod.get("attributeType"))
                if not stat:
                    continue
                val = mod.get("value") or 0.0
                if stat in bb:
                    try:
                        val = float(bb[stat])
                    except (TypeError, ValueError):
                        pass
                else:
                    snake = re.sub("([A-Z])", r"_\1", stat).lower()
                    if snake in bb:
                        try:
                            val = float(bb[snake])
                        except (TypeError, ValueError):
                            pass
                battle.add_buff(unit, {
                    "key": key, "remaining_ticks": 2,
                    "layers": 1,
                    "add": val if mod.get("formulaItem") == 0 else 0.0,
                    "mul": val if mod.get("formulaItem") == 3 else 0.0,
                    "stat": stat, "source": None,
                })

    def _apply_tile_template_buffs(self, unit, tile):
        """Terrain buffs that ride the buff-template system (mire /
        quicksand / ice / reed / deep-sea / yin-yang ...): materialise the
        tile's buffs and apply them while the unit stands on the tile."""
        battle = self.battle
        t = self.defs.get(tile.tile_key) or {}
        entries = []
        for b in (t.get("buffs") or []):
            if isinstance(b, dict) and b.get("buffKey"):
                entries.append(b)
        dbs = t.get("dynamicBuffs") or []
        if dbs:
            mi = battle.tile_mode(unit.row, unit.col)
            dbs = [dbs[mi]] if 0 <= mi < len(dbs) else []
        for db in dbs:
            for b in (db.get("buffs") or []):
                if isinstance(b, dict) and b.get("buffKey"):
                    entries.append(b)
        if not entries:
            return
        bb = battle.tile_blackboard(unit.row, unit.col) or {}
        try:
            from .buff_templates import materialise_buff
        except Exception:
            return
        for b in entries:
            key = b.get("buffKey")
            if not key or battle.buffs.get(unit, key):
                continue
            try:
                mbb = dict(bb)
                mbb.setdefault("duration", 1.0)
                entry = materialise_buff(battle, unit, dict(b), mbb, None)
                if entry and entry.get("key"):
                    battle.add_buff(unit, entry)
            except Exception:
                pass

    def _apply_infection(self, unit, tile):
        """Originum infection tiles: slow + dot (simplified)."""
        battle = self.battle
        bb = battle.tile_blackboard(unit.row, unit.col)
        dmg = float(bb.get("damage") or 80.0)
        if battle.tick % 30 == 0:
            battle.apply_damage(unit, dmg, 2, source=None)

    def _apply_hole(self, unit, tile):
        """Hole tiles: enemies (non-flying) fall down and die."""
        if getattr(unit, "side", 0) != 0:
            return
        # flying enemies ignore holes
        motion = getattr(unit, "_motion_mode", 0)
        if motion == 1:
            return
        battle = self.battle
        battle.emit(battle.tick, "enemy_falldown",
                    {"unit": unit.inst_id, "row": unit.row, "col": unit.col})
        unit._death_reason = "FALLDOWN"
        unit.take_damage(unit.hp + 1.0)   # lethal
        try:
            battle.buffs.on_owner_killed(unit)
        except Exception:
            pass

    def _apply_conveyor(self, unit, tile):
        """Conveyor tiles: push units toward the conveyor direction."""
        bb = self.battle.tile_blackboard(unit.row, unit.col)
        speed = float(bb.get("conveyor_speed") or 0.0)
        if speed <= 0:
            return
        # direction from tile key / blackboard (default: right)
        dcol = int(bb.get("conveyor_direction") or 1)
        dt = 1.0 / 30.0
        unit.pos_x += dcol * speed * dt
        unit.pos_y += 0.0
        if unit.pos_x >= self.battle.map.cols - 0.5:
            unit.pos_x = float(self.battle.map.cols - 1)
        if unit.pos_x < 0.5:
            unit.pos_x = 0.0
        unit._sync_tile() if hasattr(unit, "_sync_tile") else None

    def _apply_gravity_button(self, unit, tile):
        """Gravity button: applies a shake buff when triggered (simplified)."""
        battle = self.battle
        t = self.defs.get(tile.tile_key) or {}
        buffs = t.get("buffs") or []
        key = buffs[0].get("buffKey") if buffs else None
        if key and not battle.buffs.get(unit, key):
            battle.add_buff(unit, {"key": key, "remaining_ticks": 60,
                                   "layers": 1, "stat": None,
                                   "source": None})
