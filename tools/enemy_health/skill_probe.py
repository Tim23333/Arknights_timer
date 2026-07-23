# -*- coding: utf-8 -*-
"""敌方技能 CD 读取验证脚本 (临时调试用)

进关卡且场上有敌人后运行:
    python tools/enemy_health/skill_probe.py

验证 EnemySkill 结构偏移 (dump.cs, 未实测): m_skills 列表 -> EnemySkill
-> PeriodicTimer (period/remaining) + ESkillData (prefabKey/cd)。
源石虫等无技能敌人应显示空列表; 有技能敌人应看到 remaining 随时间倒数。
"""
import sys
import struct
import time

sys.path.insert(0, 'G:/Arknights/tools')
from enemy_health.memcore import TcpChannel          # noqa: E402
from enemy_health import game_structs as gs          # noqa: E402
from enemy_health.enemy_reader import EnemyReader, _u64, _i32   # noqa: E402


def _f32(b, o):
    return struct.unpack_from('<f', b, o)[0]


def probe(r, chan):
    mc = r.mc
    for ep in r.enemy_addrs:
        (d1, d2) = chan.batch_read([(ep + gs.EnemyFields.M_ALL_SKILLS, 8),
                                    (ep + gs.EnemyFields.M_SKILLS, 8)])
        arr_p = _u64(d1, 0) if d1 else 0
        list_p = _u64(d2, 0) if d2 else 0
        print(f'Enemy {hex(ep)} ({r._names.get(ep, ("", "?"))[1]}):')
        print(f'  m_allSkills={hex(arr_p)} m_skills={hex(list_p)}')
        # 优先 m_skills (List<EnemySkill>, 激活技能); 空则试 m_allSkills (数组)
        for tag, lp, is_arr in (('m_skills', list_p, False), ('m_allSkills', arr_p, True)):
            if not lp or not mc.is_ptr(lp):
                print(f'  {tag}: 指针无效')
                continue
            if is_arr:
                hd = chan.batch_read([(lp + gs.Il2CppArray.MAX_LENGTH, 8)])[0]
                n = _i32(hd, 0) if hd else -1
                items_p = lp + gs.Il2CppArray.ITEMS
            else:
                hd = chan.batch_read([(lp, 0x20)])[0]
                items = _u64(hd, gs.ListInternal.ITEMS) if hd else 0
                n = _i32(hd, gs.ListInternal.SIZE) if hd else -1
                items_p = items + gs.Il2CppArray.ITEMS if mc.is_ptr(items) else 0
            print(f'  {tag}: n={n}')
            if not (0 < n <= 8) or not items_p:
                continue
            items_d = chan.batch_read([(items_p, n * 8)])[0]
            if not items_d:
                continue
            for j in range(n):
                sk = _u64(items_d, j * 8)
                if not mc.is_ptr(sk):
                    print(f'    [{j}] 技能指针无效 {hex(sk)}')
                    continue
                blk = chan.batch_read([(sk, 0x90)])[0]
                if not blk:
                    continue
                timer = _u64(blk, gs.EnemySkillFields.M_COOLDOWN_TIMER)
                data = _u64(blk, gs.EnemySkillFields.DATA)
                sp_cost = _i32(blk, gs.EnemySkillFields.M_SP_COST)
                trig = _i32(blk, gs.EnemySkillFields.M_TRIGGER_CNT)
                maxtrig = _i32(blk, gs.EnemySkillFields.MAX_TRIGGER_TIME)
                period = remain = -1.0
                if mc.is_ptr(timer):
                    td = chan.batch_read([(timer, 0x20)])[0]
                    if td:
                        period = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_PERIOD_TIME))
                        remain = gs.fp_to_float(_u64(td, gs.PeriodicTimerFields.M_REMAINING_TIME))
                key = cd = initcd = None
                if mc.is_ptr(data):
                    dd = chan.batch_read([(data, 0x28)])[0]
                    if dd:
                        pk = _u64(dd, gs.ESkillDataFields.PREFAB_KEY)
                        key = mc.read_ustring(pk) if mc.is_ptr(pk) else None
                        cd = _f32(dd, gs.ESkillDataFields.COOLDOWN)
                        initcd = _f32(dd, gs.ESkillDataFields.INIT_COOLDOWN)
                print(f'    [{j}] {key!r} CD={remain:.2f}/{period:.1f}s '
                      f'(配置 cd={cd} init={initcd}) spCost={sp_cost} 触发={trig}/{maxtrig}')


def main():
    r = EnemyReader()
    r.connect()
    if not r.bootstrap():
        print('定位失败: 请确认已进入关卡且场上有敌人')
        return
    chan = TcpChannel(r.mc)
    chan.open()
    print(f'通道: {chan.mode}, 敌人: {len(r.enemy_addrs)} 个')
    probe(r, chan)
    if '--watch' in sys.argv:
        print('\n--- 3 秒后复查 remaining 是否倒数 ---')
        time.sleep(3)
        probe(r, chan)


if __name__ == '__main__':
    main()
