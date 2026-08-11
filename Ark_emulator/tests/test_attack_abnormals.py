"""Attack-attached abnormal wiring (operator_skills.apply_on_attack):
寒冷 / 沉睡 / 浮空 / 恐惧 / 束缚 from attack@ keys (cold / sleep /
levitate / fear / frozen_duration)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag, DamageType, EnemyState


def _battle(char_id, skill_index=0):
    squad = [{"charId": char_id, "phase": 2, "level": 50,
              "skillIndex": skill_index, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 100000.0
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    return sim, b


def _spawn(b, row, col):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": 0.0},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _land_attack(b, op, target):
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)


def _flag_ticks(unit, flag):
    rec = unit.abnormal.get(flag)
    return rec["ticks"] if rec else 0


def _activate(op, index):
    sc = op.skill_controller
    op.sp = sc.skills[index].sp_cost
    ok, why = sc.activate(index)
    assert ok, (index, why)


def test_aurora_s2_cold_on_hit():
    """极光 S2: 攻击对目标造成 attack@cold 秒寒冷."""
    sim, b = _battle("char_422_aurora", skill_index=1)
    b.deploy("char_422_aurora", 3, 3)
    op = b.operators[0]
    e = _spawn(b, 3, 4)
    _activate(op, 1)
    _land_attack(b, op, e)
    ticks = _flag_ticks(e, AbnormalFlag.COLD)
    assert abs(ticks - 2.5 * 30) <= 1, ticks


def test_titi_s1_sleep_probability_gated():
    """缇缇 S1: 每次攻击有 attack@prob 概率使目标沉睡 attack@sleep 秒."""
    sim, b = _battle("char_4056_titi", skill_index=0)
    b.deploy("char_4056_titi", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    _activate(op, 0)
    ticks = 0
    for _ in range(120):
        _land_attack(b, op, e)
        for _ in range(6):
            b.tick_once()
            if _flag_ticks(e, AbnormalFlag.DOZE) > 0:
                ticks = _flag_ticks(e, AbnormalFlag.DOZE)
                break
        if ticks > 0:
            break
    assert ticks > 0, "sleep must land within 120 attacks (prob 0.2)"
    assert abs(ticks - 1.5 * 30) <= 2, ticks


def test_heyyak_s2_levitate_probability_gated():
    """霍尔海雅 S2: 每发有 attack@prob 概率使目标浮空 attack@levitate 秒."""
    sim, b = _battle("char_4027_heyak", skill_index=1)
    b.deploy("char_4027_heyak", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    _activate(op, 1)
    ticks = 0
    for _ in range(150):
        _land_attack(b, op, e)
        for _ in range(6):
            b.tick_once()
            if _flag_ticks(e, AbnormalFlag.LEVITATE) > 0:
                ticks = _flag_ticks(e, AbnormalFlag.LEVITATE)
                break
        if ticks > 0:
            break
    assert ticks > 0, "levitate must land within 150 attacks (prob 0.08)"
    assert abs(ticks - 1.0 * 30) <= 2, ticks


def test_aosta_s2_root_on_hit():
    """奥斯塔 S2: 每次攻击令目标束缚 attack@frozen_duration 秒
    (game data key carries the bind duration)."""
    sim, b = _battle("char_346_aosta", skill_index=1)
    b.deploy("char_346_aosta", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    _activate(op, 1)
    _land_attack(b, op, e)
    for _ in range(20):
        b.tick_once()
        if _flag_ticks(e, AbnormalFlag.UNMOVABLE) > 0:
            break
    ticks = _flag_ticks(e, AbnormalFlag.UNMOVABLE)
    assert abs(ticks - 0.8 * 30) <= 1, ticks


def test_buff_prob_gates_stun():
    """推进之王 S3: 每次攻击有 attack@buff_prob=0.4 概率晕眩目标
    attack@stun=0.5s - the stun must NOT land on every attack."""
    sim, b = _battle("char_112_siege", skill_index=2)
    b.deploy("char_112_siege", 3, 3)
    op = b.operators[0]
    e = _spawn(b, 3, 4)
    _activate(op, 2)
    stunned = 0
    for _ in range(30):
        _land_attack(b, op, e)
        if _flag_ticks(e, AbnormalFlag.STUNNED) > 0:
            stunned += 1
        # expire the 0.5s stun (15 ticks) before the next attack so each
        # check reflects only that attack's stun roll
        for _ in range(16):
            b.tick_once()
    assert 0 < stunned < 30, stunned


def test_radian_s3_magic_fragility_on_hit():
    """电弧 S3: 对敌人造成伤害时施加停顿 2s 与 10% 法术脆弱 2s
    (game template weak[magic][limit] -> DamageScale damage_scale 1.1)."""
    sim, b = _battle("char_4195_radian", skill_index=2)
    b.deploy("char_4195_radian", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    _activate(op, 2)
    _land_attack(b, op, e)
    for _ in range(20):
        b.tick_once()
        if b.buffs.get(e, "weak[magic][limit]"):
            break
    rec = b.buffs.get(e, "weak[magic][limit]")
    assert rec is not None, "magic fragility must apply on hit"
    assert abs((rec.get("blackboard") or {}).get(
        "damage_scale", 0.0) - 1.1) < 1e-9, rec
    assert abs(rec["remaining_ticks"] - 2.0 * 30) <= 2, rec
    # magic damage taken is multiplied by 1.1
    hp0 = e.hp
    b.apply_damage(e, 1000.0, DamageType.MAGICAL, source=op)
    # mres 20 -> base 800, fragility 1.1 -> 880
    assert abs((hp0 - e.hp) - 880.0) < 1e-6, (hp0 - e.hp)


def test_cuttle_s2_move_speed_debuff_on_hit():
    """安哲拉 S2: 被击中的目标 attack@duration 秒内移动速度
    -20% (attack@move_speed -0.2, moveSpeed is a 1.0-base ratio)."""
    sim, b = _battle("char_218_cuttle", skill_index=1)
    b.deploy("char_218_cuttle", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    base_ms = e.attributes.get("moveSpeed")
    _activate(op, 1)
    _land_attack(b, op, e)
    for _ in range(30):
        b.tick_once()
        if b.buffs.get(e, "op_skill_atk_move_speed"):
            break
    rec = b.buffs.get(e, "op_skill_atk_move_speed")
    assert rec is not None, "move-speed debuff must apply on hit"
    assert abs(rec["mul"] + 0.2) < 1e-9, rec
    assert abs(rec["remaining_ticks"] - 3.0 * 30) <= 2, rec
    assert abs(e.attributes.get("moveSpeed") - base_ms * 0.8) < 1e-6, \
        (base_ms, e.attributes.get("moveSpeed"))


def test_sesa_s2_attack_speed_debuff_on_hit():
    """慑砂 S2: 榴弹爆炸后 attack@duration 秒内目标攻击速度 -3
    (attackSpeed is a 100-base percentage, additive layer)."""
    sim, b = _battle("char_379_sesa", skill_index=1)
    b.deploy("char_379_sesa", 2, 3)
    op = b.operators[0]
    e = _spawn(b, 2, 5)
    _activate(op, 1)
    _land_attack(b, op, e)
    for _ in range(60):
        b.tick_once()
        if b.buffs.get(e, "op_skill_atk_attack_speed"):
            break
    rec = b.buffs.get(e, "op_skill_atk_attack_speed")
    assert rec is not None, "attack-speed debuff must apply on hit"
    assert abs(rec["add"] + 3.0) < 1e-9, rec
    assert abs(rec["remaining_ticks"] - 3.0 * 30) <= 2, rec
    assert abs(e.attributes.get("attackSpeed") - 97.0) < 1e-6, \
        e.attributes.get("attackSpeed")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    import traceback
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
