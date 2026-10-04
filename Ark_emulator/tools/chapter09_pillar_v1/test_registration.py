"""Actual9-18 duplicate aliases become three distinct native-record actors."""
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'unpack_work/campaign_c9_foundation_v9_candidate'))
sys.path.insert(1, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.stage_converter_reusable_v2 import map_plan
from tools.chapter09_pillar_v1.registration import registrations, resolve_reference
from tools.chapter09_pillar_v1.build_payload import build, providers
from tools.chapter09_pillar_v1.bigforce import build as field_build, providers as field_providers, profile as field_profile


def source_profile():
    source = json.loads((ROOT / 'packages/campaign/chapter09_source_prepare/source.plan.v1.json').read_bytes())
    native = source['stages']['level_main_09-16']['native_document']
    profile = registrations('main_09-16', native, {'trap_043_dupilr': 'unit/ch9/pillar/body'})
    return native, profile


def test_native_duplicate_alias_preserved_but_ambiguous_lookup_rejected():
    native, profile = source_profile()
    assert len(profile['records']) == 3
    assert [r['raw_alias'] for r in profile['records']] == ['trap_043_dupilr#1'] * 3
    assert [r['raw_native'] for r in profile['records']] == native['predefines']['tokenInsts']
    assert len({r['registration_key'] for r in profile['records']}) == 3
    with pytest.raises(ValueError, match='ambiguous'):
        resolve_reference(profile, alias='trap_043_dupilr#1')
    for r in profile['records']:
        assert resolve_reference(profile, record_key=r['registration_key']) == r['registration_key']


def test_actual_three_native_record_entities_disk_cp_and_public_head(tmp_path):
    native, profile = source_profile(); package = build()
    # This case proves raw record identity and coordinate conversion. Full
    # native-map admission separately requires tile_bigforce's real consumer.
    grid = native['mapData']['map']; plan = {'rows': len(grid), 'cols': len(grid[0])}
    package['scenarioDraft'] = {'id': 'scene/pillar/native_registration', 'ruleset': 'ruleset/ark_standard',
        'map': plan, 'initialEntities': [r['initial_entity'] for r in profile['records']]}
    sim = Engine.create(Compiler(providers=providers()).compile(package), providers=providers())
    registry = sim.ctx.state()['predefined_registry']
    assert set(registry) == {r['registration_key'] for r in profile['records']}
    assert len(set(registry.values())) == 3
    sim.advance(2)
    path = tmp_path / 'native_records.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    restored = Engine.restore(sim.program, json.loads(path.read_bytes()), providers=providers())
    sim.advance(3); restored.advance(3)
    assert sim.checkpoint() == restored.checkpoint() == replay(sim.program, sim.export_replay(), providers=providers()).checkpoint()


def test_native_map_keeps_bigforce_tiles_and_registers_three_records(tmp_path):
    native, profile = source_profile(); package = build(); fields = field_build()
    for key, values in fields.items():
        if key not in {'schemaVersion', 'manifest'}:
            package.setdefault(key, []).extend(values)
    plan = map_plan(native); plan.pop('coordinate_conversion')
    plan['tile_mechanics'] = {'tile_bigforce': field_profile()}
    package['scenarioDraft'] = {'id': 'scene/pillar/native_map_registration', 'ruleset': 'ruleset/ark_standard',
        'map': plan, 'initialEntities': [r['initial_entity'] for r in profile['records']]}
    reg = {**providers(), **field_providers()}; program = Compiler(providers=reg).compile(package)
    sim = Engine.create(program, providers=reg); sim.advance(2)
    assert len(sim.ctx.state()['predefined_registry']) == 3 and len(sim.ctx.state()['tile_fields']) == 2
    assert sum(tile['tileKey'] == 'tile_bigforce' for tile in program.scenario['map']['tiles']) == 2
    path = tmp_path / 'native_map.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    resumed = Engine.restore(program, json.loads(path.read_bytes()), providers=reg); sim.advance(3); resumed.advance(3)
    assert sim.checkpoint() == resumed.checkpoint() == replay(program, sim.export_replay(), providers=reg).checkpoint()
