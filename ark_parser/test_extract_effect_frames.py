# -*- coding: utf-8 -*-
import unittest
import struct

from ark_parser.extract_effect_frames import normalize_enemy_database, parse_skel_events


class EffectFrameDataTests(unittest.TestCase):
    def test_spine_event_uses_big_endian_float_time(self):
        def text(value):
            encoded = value.encode('utf-8')
            return bytes([len(encoded) + 1]) + encoded
        # Minimal Spine 3.8 skeleton: one event and one event-only animation.
        raw = (b'\0' + text('3.8.99') + struct.pack('>4f', 0, 0, 0, 0) + b'\0'
               + b'\1' + text('OnAttack') + b'\0' * 7
               + b'\1\1\0' + struct.pack('>f', 0) + b'\0\0'
               + b'\1' + text('Skill_1') + b'\0' * 7
               + b'\1' + struct.pack('>f', 4 / 3) + b'\0\0'
               + struct.pack('>f', 0) + b'\0')
        result = parse_skel_events(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result['Skill_1']['ev'], [{'n': 'OnAttack', 't': 1.3333, 'f': 40.0}])
    def test_open_arknights_enemy_rows_are_normalized(self):
        payload = {
            'enemies': [{
                'Key': 'enemy_1_test',
                'Value': [{
                    'level': 2,
                    'enemyData': {
                        'skills': [{'prefabKey': 'SkillA'}],
                    },
                }],
            }],
        }

        result = normalize_enemy_database(payload)

        self.assertEqual(
            result['enemy_1_test'][0]['data']['skills'][0]['prefabKey'],
            'SkillA')
        self.assertEqual(result['enemy_1_test'][0]['level'], 2)

    def test_native_mapping_is_unchanged(self):
        payload = {'enemy_1_test': [{'data': {'skills': []}}]}
        self.assertIs(normalize_enemy_database(payload), payload)


if __name__ == '__main__':
    unittest.main()
