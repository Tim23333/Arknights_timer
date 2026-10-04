"""The whole-Boss checklist preserves source references and real gaps."""
import json
from tools.chapter08_joint_v3.build_bsnake_requirements_v1 import build, OUT


def test_exact_requirements_rebuild_preserves_four_modes_and_eleven_templates():
    value = json.loads(OUT.read_bytes())
    assert value == build()
    assert [mode['index'] for mode in value['source_modes']] == [0, 1, 2, 3]
    assert len(value['source_buff_graph']) == 11
    assert len(value['source_hint_aliases']) == 7
    assert all(len(group) == 5 for group in value['source_hint_aliases'])
    assert value['source_modes'][0]['resolved_animations']['_attack']['events'][0]['frame'] == 31
    assert value['source_reborn']['raw']['_extraRebornDataPresets'][0]['hpRechargeRatio'] == 0
    assert value['source_skill_profiles']['SummonFlame']['cooldown'] == 50
    assert value['source_skill_profiles']['SummonFlame']['initCooldown'] == 75
    assert len(value['requirements']) == 9
    assert value['full_boss_complete'] is False and value['whole_stage_executed'] is False
