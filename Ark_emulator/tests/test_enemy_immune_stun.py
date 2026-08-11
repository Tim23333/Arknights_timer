"""EnemySkill._immuneStunWhenAffecting: while a stun-immune enemy skill
is being cast, incoming stuns are ignored (dump.cs EnemySkill 0x39)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator import Simulator
from ark_emulator.consts import AbnormalFlag, EnemyState


def test_enemy_stun_immune_while_casting():
    """施放中免疫眩晕，施放结束恢复可被眩晕."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1000_gopro", 0)
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    # buff 层：施放中免疫标记存在时眩晕被忽略
    e._immune_stun_affecting = True
    b.add_abnormal(e, AbnormalFlag.STUNNED, 2.0)
    assert not e.flag(int(AbnormalFlag.STUNNED)), "stun must be ignored"
    # 施放结束（清除标记）后眩晕可施加
    e._immune_stun_affecting = False
    b.add_abnormal(e, AbnormalFlag.STUNNED, 2.0)
    assert e.flag(int(AbnormalFlag.STUNNED)), "stun applies after cast"
    print("OK enemy stun-immune while casting")


def test_cast_sets_immune_flag():
    """_start_cast 按技能 _immuneStunWhenAffecting 设置施放免疫标记."""
    sim = Simulator(level_id="level_main_01-01")
    sim.run_ticks(15)
    b = sim.battle
    b.spawn_enemy("enemy_1505_frstar", 0)   # 霜星（5 技能）
    e = b.enemies[-1]
    e.state = EnemyState.COMBAT
    sc = e.skill_controller
    assert sc is not None and sc.skills
    s = sc.skills[0]
    s.immune_stun_when_affecting = True
    sc._start_cast((s, None))
    assert getattr(e, "_immune_stun_affecting", False)
    print("OK _start_cast sets immune flag")


if __name__ == "__main__":
    test_enemy_stun_immune_while_casting()
    test_cast_sets_immune_flag()
