"""attack@def / attack@atk activation stat buffs (summon/allied targets)
and Ch'en slime field:

  - kalts_3: Mon3tr def +100% / atk +130% (attack@def 1.0 / attack@atk 1.3)
  - bstalk_2: Beanstalk crabs def +20% (attack@def 0.2)
  - necras_3: servant atk +80% / def +40% / maxHp +80%
  - pallas_3: front-tile ally def +15% (attack@def 0.15)
  - chen2 S2/S3: slime field debuffs moveSpeed (mul) + def (add) 5s
  - attack@atk is a buff, NOT extra flat damage on every hit
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import EnemyState


def _battle(char_id, skill_index):
    squad = [{"charId": char_id, "phase": 2, "level": 50,
              "skillIndex": skill_index, "skillLevels": [1, 1, 1]}]
    sim = Simulator(level_id="level_main_01-01", squad=squad)
    sim.run_ticks(15)
    b = sim.battle
    b.max_cost = 1e6
    b.cost = 0.0
    b.cost_increase_time = 1e7
    b.battle_cost_add(100.0)
    for (r, c) in [(2, 3), (3, 3), (1, 3), (3, 2), (2, 4)]:
        ok = b.deploy(char_id, r, c)
        if ok[0]:
            break
    op = b.operators[0]
    return sim, b, op


def _spawn_token(b, token_key, op, row=3, col=4):
    ok, pid = b.spawn_token_forced(token_key, row, col, owner=op)
    assert ok, (token_key, ok)
    return [t for t in b.tokens if not t.dead][-1]


def _activate(op, index):
    sc = op.skill_controller
    op.sp = sc.skills[index].sp_cost
    ok, why = sc.activate(index)
    assert ok, why


def _spawn_enemy(b, row, col, def_v=0.0):
    b.spawn_enemy("enemy_1000_gopro", 0, overrides={
        "attributes": {"maxHp": 50000.0, "atk": 0.0, "def": def_v},
        "row": row, "col": col})
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    return e


def _attack_hit(b, op, target):
    """Resolve one attack; returns whether it spawned a projectile."""
    b._operator_attack(op, target, op.attributes.attack_interval())
    pa = op._pending_attack
    while pa["remaining"] > 0:
        pa["remaining"] -= 1
    b._resolve_operator_attack(op, pa)
    return bool(pa.get("ranged"))


def test_kalts3_mon3tr_def_and_atk():
    """凯尔希 S3：Mon3tr 防御 +100%、攻击 +130%."""
    sim, b, op = _battle("char_003_kalts", 2)
    tok = _spawn_token(b, "token_10002_kalts_mon3tr", op)
    d0, a0 = tok.attributes.get("def"), tok.attributes.get("atk")
    _activate(op, 2)
    assert abs(tok.attributes.get("def") - d0 * 2.0) < 0.01
    assert abs(tok.attributes.get("atk") - a0 * 2.3) < 0.01
    print("OK kalts3 Mon3tr def %s->%s atk %s->%s" % (
        d0, tok.attributes.get("def"), a0, tok.attributes.get("atk")))


def test_bstalk2_crab_def():
    """豆苗 S2：所有磐蟹防御 +20%."""
    sim, b, op = _battle("char_452_bstalk", 1)
    crab1 = _spawn_token(b, "token_10014_bstalk_crab", op, 3, 4)
    crab2 = _spawn_token(b, "token_10014_bstalk_crab", op, 4, 4)
    d0 = crab1.attributes.get("def")
    _activate(op, 1)
    assert abs(crab1.attributes.get("def") - d0 * 1.2) < 0.01
    assert abs(crab2.attributes.get("def") - d0 * 1.2) < 0.01
    print("OK bstalk crabs def %s -> %s" % (d0, crab1.attributes.get("def")))


def test_necras3_servant_buffs():
    """死芒 S3：悲叹的仆役 atk +80% / def +40% / maxHp +80%."""
    sim, b, op = _battle("char_450_necras", 2)
    tok = _spawn_token(b, "token_10043_necras_skeltn", op)
    a0, d0, h0 = (tok.attributes.get("atk"), tok.attributes.get("def"),
                  tok.attributes.get("maxHp"))
    _activate(op, 2)
    assert abs(tok.attributes.get("atk") - a0 * 1.8) < 0.01
    assert abs(tok.attributes.get("def") - d0 * 1.4) < 0.01
    assert abs(tok.attributes.get("maxHp") - h0 * 1.8) < 0.01
    print("OK necras servant atk/def/maxHp scaled")


def test_pallas3_front_ally_def():
    """帕拉斯 S3：身前一格近战位友方防御 +15%."""
    sim, b, pallas = _battle("char_485_pallas", 2)
    ok = b.deploy("char_149_scave", 3, 4)   # 身前一格（面向右）
    assert ok[0], ok
    ally = [o for o in b.operators if o.inst_id != pallas.inst_id][-1]
    d0 = ally.attributes.get("def")
    _activate(pallas, 2)
    assert abs(ally.attributes.get("def") - d0 * 1.15) < 0.01
    print("OK pallas front ally def %s -> %s" % (
        d0, ally.attributes.get("def")))


def _slime_checks(sim, b, op, e, expect_ms, expect_def):
    ranged = _attack_hit(b, op, e)
    if ranged:
        for _ in range(30):
            sim.run_ticks(1)
            if not any(not p.dead for p in getattr(b, "projectiles", [])):
                break
    ms = [x for x in (getattr(e, "buffs", None) or [])
          if x.get("key") == "op_slime_field"]
    df = [x for x in (getattr(e, "buffs", None) or [])
          if x.get("key") == "op_slime_field_def"]
    assert ms and df, (ms, df)
    assert abs(float(ms[0]["mul"]) - expect_ms) < 1e-6, ms
    assert abs(float(df[0]["add"]) - expect_def) < 1e-6, df
    assert ms[0]["remaining_ticks"] == 150   # 5s * 30
    return e.attributes.get("def")


def test_chen2_s2_slime_field():
    """假日威龙陈 S2：粘液 -10% 移速 / -50 防御 5s."""
    sim, b, op = _battle("char_1013_chen2", 1)
    e = _spawn_enemy(b, op.row, op.col + 1, def_v=100.0)
    _activate(op, 1)
    def_after = _slime_checks(sim, b, op, e, -0.1, -50.0)
    assert abs(def_after - 50.0) < 0.01
    print("OK chen2 S2 slime: def", def_after)


def test_chen2_s3_slime_field():
    """假日威龙陈 S3：粘液 -20% 移速 / -100 防御 5s."""
    sim, b, op = _battle("char_1013_chen2", 2)
    e = _spawn_enemy(b, op.row, op.col + 1, def_v=200.0)
    _activate(op, 2)
    def_after = _slime_checks(sim, b, op, e, -0.2, -100.0)
    assert abs(def_after - 100.0) < 0.01
    print("OK chen2 S3 slime: def", def_after)


def test_attack_atk_not_extra_damage():
    """attack@atk 是增益不是额外伤害：catap2_2 命中不产生 0.55 点伤害."""
    sim, b, op = _battle("char_1049_catap2", 1)
    e = _spawn_enemy(b, op.row, op.col + 1)
    _activate(op, 1)
    atk = op.attributes.get("atk")
    hp0 = e.hp
    _attack_hit(b, op, e)
    if any(not p.dead for p in getattr(b, "projectiles", [])):
        for _ in range(30):
            sim.run_ticks(1)
            if not any(not p.dead for p in b.projectiles):
                break
    dealt = hp0 - e.hp
    # 普攻伤害 = 攻击力，无 0.55 额外伤害（旧实现会多打 atk*0+0.55）
    assert dealt > 0 and abs(dealt - atk) < 0.5, (dealt, atk)
    print("OK catap2_2 hit damage:", dealt)


if __name__ == "__main__":
    test_kalts3_mon3tr_def_and_atk()
    test_bstalk2_crab_def()
    test_necras3_servant_buffs()
    test_pallas3_front_ally_def()
    test_chen2_s2_slime_field()
    test_chen2_s3_slime_field()
    test_attack_atk_not_extra_damage()
