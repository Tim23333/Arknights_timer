"""Damage settlement (physical/magical/true/element).

Game-standard formulas (BattleFormula exists in dump.cs but body not visible;
these are the standard Arknights formulas - see TODO in README):
  physical: max(PHYS_MIN_DAMAGE_RATIO * atkEff, atkEff - defEff)
  magical : max(PHYS_MIN_DAMAGE_RATIO * atkEff,
                atkEff * max(0, 1 - mresEff/100))
  true    : atkEff
Both physical and magical damage keep a 5% minimum of the effective ATK
(x atk scale) when mitigation would reduce the hit below the floor
(NGA/PRTS formula; mres 100 still deals 5% polish damage).
"""

from .consts import DamageType, PHYS_MIN_DAMAGE_RATIO


class DamageResult:
    __slots__ = ("amount", "type", "critical", "dodged", "source", "target")

    def __init__(self, amount, type_, critical=False, dodged=False,
                 source=None, target=None):
        self.amount = amount
        self.type = type_
        self.critical = critical
        self.dodged = dodged
        self.source = source
        self.target = target

    def to_dict(self):
        return {"amount": round(self.amount, 3), "type": self.type,
                "critical": self.critical, "dodged": self.dodged}


def calculate_damage(atk, target_attrs, damage_type, atk_scale=1.0,
                     atk_addition=0.0, penetrate_ratio=0.0, penetrate_fixed=0.0):
    """Compute damage before hitrate/dodge rolls."""
    atk_eff = atk * atk_scale + atk_addition
    atk_eff = max(0.0, atk_eff)
    if damage_type == DamageType.PHYSICAL:
        def_eff = max(0.0, target_attrs.get("def") * (1 - penetrate_ratio) - penetrate_fixed)
        return max(atk_eff * PHYS_MIN_DAMAGE_RATIO, atk_eff - def_eff)
    if damage_type == DamageType.MAGICAL:
        mres = max(0.0, target_attrs.get("magicResistance") - penetrate_fixed) * (1 - penetrate_ratio)
        mres = min(100.0, mres)
        return max(atk_eff * PHYS_MIN_DAMAGE_RATIO,
                   atk_eff * max(0.0, 1.0 - mres / 100.0))
    if damage_type == DamageType.TRUE:
        return atk_eff
    raise ValueError(f"unknown damage type {damage_type}")


def roll_damage(unit, atk, damage_type, atk_scale=1.0, atk_addition=0.0,
                rng=None, critical_chance=0.0, dodge_chance=0.0):
    """Full damage roll incl. hitrate/crit/dodge hooks (defaults off)."""
    if rng is not None and dodge_chance > 0 and rng.chance(dodge_chance):
        return DamageResult(0, damage_type, dodged=True, source=unit)
    critical = rng is not None and critical_chance > 0 and rng.chance(critical_chance)
    amount = calculate_damage(atk, unit.attributes, damage_type, atk_scale, atk_addition)
    if critical:
        amount *= 1.5  # default crit multiplier (TODO confirm per-source)
    return DamageResult(amount, damage_type, critical=critical, source=unit)
