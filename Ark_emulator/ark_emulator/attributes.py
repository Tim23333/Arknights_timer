"""Attribute model with buff-driven modifiers.

Modifiers are keyed per stat; effective value is computed on demand from the
base value + additive/multiplicative contributions (Arknights-style).
attackSpeed is a percentage base (100); attack interval =
baseAttackTime * 100 / attackSpeed (04 doc, INFERRED formula).
"""


class Attributes:
    FIELDS = (
        "maxHp", "atk", "def", "magicResistance", "cost", "blockCnt",
        "moveSpeed", "attackSpeed", "baseAttackTime", "respawnTime",
        "hpRecoveryPerSec", "spRecoveryPerSec", "maxDeployCount", "massLevel",
        "baseForceLevel", "tauntLevel", "epDamageResistance", "epResistance",
        "maxEp",
        "damageHitratePhysical", "damageHitrateMagical", "epBreakRecoverSpeed",
        "defPenetrate", "defPenetrateFixed", "magicResistPenetrate",
        "magicResistPenetrateFixed",
        "rangeRadius", "viewRadius", "invisible", "invincible", "undeadable",
        "healFree", "unmovable", "blockFree", "stunImmune", "silenceImmune",
        "sleepImmune", "frozenImmune",
        "levitateImmune", "disarmedCombatImmune", "fearedImmune", "palsyImmune",
        "attractImmune", "teleportImmune", "groundBoundImmune",
    )
    IMMUNE_FIELDS = (
        "stunImmune", "silenceImmune", "sleepImmune", "frozenImmune",
        "levitateImmune", "disarmedCombatImmune", "fearedImmune", "palsyImmune",
        "attractImmune", "teleportImmune", "groundBoundImmune",
    )

    LAYERS = ("add", "mul", "final_add", "final_mul")

    def __init__(self, data=None):
        data = data or {}
        self.base = {f: (data.get(f) if data.get(f) is not None else 0)
                     for f in self.FIELDS}
        self._mods = {}  # stat -> list of (layer, value, key)

    # ---- modifier management ----
    def add_modifier(self, stat, additive=0.0, multiplicative=0.0,
                     final_add=0.0, final_mul=0.0, key=None):
        """Four-layer Arknights model (MECHANICS 2.2):
        add (????) -> mul (????, percentages add) ->
        final_add (????) -> final_mul (????, multiply)."""
        layer_vals = ((self.LAYERS[0], additive), (self.LAYERS[1], multiplicative),
                      (self.LAYERS[2], final_add), (self.LAYERS[3], final_mul))
        for layer, val in layer_vals:
            if val:
                self._mods.setdefault(stat, []).append((layer, val, key))

    def remove_modifier(self, key):
        for stat in list(self._mods):
            self._mods[stat] = [m for m in self._mods[stat] if m[2] != key]

    def clear(self):
        self._mods.clear()

    # ---- effective values ----
    def get(self, stat):
        v = self.base[stat]
        add = 0.0
        mul = 1.0
        fadd = 0.0
        fmul = 1.0
        for layer, val, _k in self._mods.get(stat, ()):
            if layer == "add":
                add += val
            elif layer == "mul":
                mul *= (1.0 + val)
            elif layer == "final_add":
                fadd += val
            elif layer == "final_mul":
                fmul *= val
        return ((v + add) * mul + fadd) * fmul

    def get_bool(self, stat):
        return bool(self.base.get(stat))

    def immune(self, flag_field):
        return bool(self.base.get(flag_field))

    def attack_interval(self):
        spd = self.get("attackSpeed")
        if spd <= 0:
            spd = 100.0
        return self.get("baseAttackTime") * 100.0 / spd

    def to_dict(self, stats=None):
        stats = stats or self.FIELDS
        return {s: round(self.get(s), 4) for s in stats}
