# -*- coding: utf-8 -*-
"""生效帧展示 (backend/app/effect_frames_ui.py) 测试。

依赖 data/tables/effect_frames.json（ark_parser/extract_effect_frames.py 产物），
文件缺失时整组跳过。
"""

import os
import unittest

from backend.app.effect_frames_ui import (
    character_frame_rows, enemy_frame_rows,
)

DATA_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'data', 'tables', 'effect_frames.json')


@unittest.skipUnless(os.path.isfile(DATA_JSON), 'effect_frames.json 未生成')
class EffectFrameRowsTests(unittest.TestCase):
    def test_unknown_id_returns_empty(self):
        self.assertEqual(enemy_frame_rows('enemy_nonexistent_zzz'), [])
        self.assertEqual(character_frame_rows('char_nonexistent_zzz'), [])

    def test_faust_skill_frames(self):
        rows = enemy_frame_rows('enemy_1508_faust')
        by_label = {row[0]: row for row in rows}
        # CriticalHit: Skill_1 动画 OnAttack 1.3333s = 40帧, 弹道 10 格/秒
        crit = by_label.get('CriticalHit')
        self.assertIsNotNone(crit)
        self.assertIn('Skill_1', crit[1])
        self.assertIn('40帧', crit[3])
        self.assertIn('projectile_faust_s1', crit[4])
        self.assertIn('3 帧/格', crit[5])
        self.assertIn('距离×3帧', crit[6])
        # SummonBallis: Skill_2 动画 OnAttack 0.9s = 27帧, 无弹道
        summon = by_label.get('SummonBallis')
        self.assertIsNotNone(summon)
        self.assertIn('Skill_2', summon[1])
        self.assertIn('27帧', summon[3])

    def test_amiya_modes_and_fixed_fly_time(self):
        rows = character_frame_rows('char_002_amiya')
        by_label = {row[0]: row for row in rows}
        normal = by_label.get('普攻')
        self.assertIsNotNone(normal)
        self.assertIn('0.483', normal[2])           # preDelay 起手
        self.assertIn('固定飞行', normal[5])        # 定时型弹道
        # mode 名映射技能名
        self.assertTrue(any('精神爆发' in row[0] for row in rows))
        self.assertTrue(any('奇美拉' in row[0] for row in rows))

    def test_anim_variant_prefix_match(self):
        # 凛御银灰普攻 animKey=Attack, 实际动画为 Attack_A/B/C 变体
        rows = character_frame_rows('char_1045_svash2')
        normal = next((row for row in rows if row[0] == '普攻'), None)
        self.assertIsNotNone(normal)
        self.assertIn('Attack_A', normal[3])

    def test_unreferenced_skill_anims_listed(self):
        # Skill_3_Combat 未被 mode 引用, 应以「动画 Skill_3_Combat」补充行出现
        rows = character_frame_rows('char_1045_svash2')
        self.assertTrue(any(row[0] == '动画 Skill_3_Combat' for row in rows))


if __name__ == '__main__':
    unittest.main()
