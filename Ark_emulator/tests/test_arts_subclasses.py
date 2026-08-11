# -*- coding: utf-8 -*-
"""Arts subclass trait tests:
- artsfghter (\u6cd5\u672f\u8fd1\u536b) / artsprotector (\u6cd5\u672f\u91cd\u88c5):
  basic attacks deal MAGICAL damage (ignore DEF).
- splashcaster (\u6269\u6563\u672f\u5e08): basic attack is MAGICAL and splashes
  the target tile (neighbours take full ATK too).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import DamageType, EnemyState


def _battle():
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    b.waves._idx = len(b.waves.timeline)
    b.waves.finished = True
    return sim, b


def _spawn(b, row, col, hp=50000.0, defense=500.0, mr=0.0):
    b.spawn_enemy("enemy_1000_gopro_2", 0, overrides={
        "attributes": {"maxHp": hp, "atk": 0.0, "def": defense,
                       "magicResistance": mr, "moveSpeed": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_melee(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def test_artsfghter_magical_damage_ignores_def():
    sim, b = _battle()
    b.deploy("char_185_frncat", 3, 3)         # \u6155\u65af (artsfghter)
    op = b.operators[0]
    assert b._char_damage_type(op) == DamageType.MAGICAL
    atk = float(op.attributes.get("atk"))
    e = _spawn(b, 3, 4, defense=500.0)
    _land_melee(b, op, e)
    assert abs((50000.0 - e.hp) - atk) < 0.01, (e.hp, atk)


def test_artsprotector_magical_damage_ignores_def():
    sim, b = _battle()
    b.deploy("char_260_durnar", 3, 3)         # \u575a\u96f7 (artsprotector)
    op = b.operators[0]
    assert b._char_damage_type(op) == DamageType.MAGICAL
    atk = float(op.attributes.get("atk"))
    e = _spawn(b, 3, 4, defense=500.0)
    _land_melee(b, op, e)
    assert abs((50000.0 - e.hp) - atk) < 0.01, (e.hp, atk)


def test_splashcaster_splash_and_magical():
    sim, b = _battle()
    b.deploy("char_121_lava", 2, 3)           # \u708e\u7194 (splashcaster)
    op = b.operators[0]
    ts = op.trait_system
    assert ts.is_splashcaster()
    assert b._char_damage_type(op) == DamageType.MAGICAL
    atk = float(op.attributes.get("atk"))
    main = _spawn(b, 2, 4, defense=500.0)
    near = _spawn(b, 1, 4, defense=500.0)
    far = _spawn(b, 6, 6, defense=500.0)
    b._operator_attack(op, main, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    # ranged: wait for the projectile to land (splash fires on projectile hit)
    for _ in range(60):
        b.tick_once()
        if not b.projectiles:
            break
    assert abs((50000.0 - main.hp) - atk) < 0.01, main.hp
    assert abs((50000.0 - near.hp) - atk) < 0.01, near.hp
    assert far.hp == 50000.0, far.hp
    assert any(x["type"] == "attack"
               and (x.get("data") or {}).get("type") == "splashcaster_splash"
               for x in b.events.snapshot_events())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        print("=" * 30, fn.__name__)
        fn()
    print("ALL OK")
