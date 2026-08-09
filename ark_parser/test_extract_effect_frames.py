# -*- coding: utf-8 -*-
import unittest

from ark_parser.extract_effect_frames import normalize_enemy_database


class EffectFrameDataTests(unittest.TestCase):
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
