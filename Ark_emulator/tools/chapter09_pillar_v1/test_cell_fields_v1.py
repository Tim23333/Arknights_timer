"""Actual9-18 duplicate aliases become three distinct native-record actors."""
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'unpack_work/campaign_c9_cell_fields_v1_candidate'))
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
    fence = next(t for t in plan['tiles'] if t['tileKey'] == 'tile_fence')
    plan['tile_mechanics']['tile_fence'] = {'type': 'declared_static_tile',
        'expected_options': {k: fence[k] for k in ('buildableType', 'passableMask', 'heightType')},
        'expected_blackboard': fence['blackboard'], 'expected_effects': fence['effects']}
    plan['tile_cell_mechanics'] = {str(index // plan['cols'])+':'+str(index % plan['cols']): field_profile() for index, tile in enumerate(plan['tiles']) if tile.get('blackboard')}
    package['scenarioDraft'] = {'id': 'scene/pillar/native_map_registration', 'ruleset': 'ruleset/ark_standard',
        'map': plan, 'initialEntities': [r['initial_entity'] for r in profile['records']]}
    reg = {**providers(), **field_providers()}; program = Compiler(providers=reg).compile(package)
    sim = Engine.create(program, providers=reg); sim.advance(2)
    assert len(sim.ctx.state()['predefined_registry']) == 3 and len(sim.ctx.state()['tile_fields']) == 4
    assert sum(tile['tileKey'] == 'tile_bigforce' for tile in program.scenario['map']['tiles']) == 2
    path = tmp_path / 'native_map.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    resumed = Engine.restore(program, json.loads(path.read_bytes()), providers=reg); sim.advance(3); resumed.advance(3)
    assert sim.checkpoint() == resumed.checkpoint() == replay(program, sim.export_replay(), providers=reg).checkpoint()


@pytest.mark.parametrize('key', ['00:0', '0:-1', '1:0', '0:2', '0:0:0', 'cell'])
def test_invalid_or_outside_cell_identity_rejected(key):
    from ark_sim.domains.tile_mechanics import validate_cell_profiles
    with pytest.raises(ValueError):
        validate_cell_profiles({'rows': 1, 'cols': 2, 'tile_cell_mechanics': {key: field_profile()}})


def test_cell_override_cannot_claim_unimplemented_periodic_or_portal_dispatch():
    from ark_sim.domains.tile_mechanics import validate_cell_profiles
    with pytest.raises(ValueError):
        validate_cell_profiles({'rows': 1, 'cols': 1, 'tile_cell_mechanics': {'0:0': {
            'type': 'route_checkpoint_portal', 'role': 'entry'}}})


def test_cell_profile_requires_exact_native_operand_and_explicit_tiles():
    p = field_build(); p['scenarioDraft'] = {'id': 'scene/cellfield/invalid', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 1, 'cols': 1, 'tile_cell_mechanics': {'0:0': field_profile()}}}
    with pytest.raises(ValueError):
        Compiler(providers=field_providers()).compile(p)
    p['scenarioDraft']['map']['tiles'] = [{'tileKey': 'tile_floor', 'blackboard': {'base_force_level': 2.0}}]
    with pytest.raises(ValueError):
        Compiler(providers=field_providers()).compile(p)


def test_native_9_19_road_infection_operand_is_consumed_without_tilekey_rewrite(tmp_path):
    from tools.chapter09_pillar_v1.build_map_profile import build as map_build
    from tools.chapter08_environment.policies_v1 import providers as infection_providers
    source = json.loads((ROOT / 'packages/campaign/chapter09_source_prepare/source.plan.v1.json').read_bytes())
    native = source['stages']['level_main_09-17']['native_document']; plan = map_build(native)
    assert len(plan['tile_cell_mechanics']) == 1
    key = next(iter(plan['tile_cell_mechanics'])); row, col = map(int, key.split(':'))
    assert plan['tiles'][row * plan['cols'] + col]['tileKey'] == 'tile_road'
    package = {'schemaVersion': 2, 'entities': [{'id': 'unit/c9/infection/probe', 'kind': 'entity', 'tags': ['player'],
        'components': {'attributes': {'base': {'max_hp': 20000, 'atk': 200, 'def': 137, 'mres': 23, 'attack_speed_ratio': 1}},
            'resources': {'hp': {'role': 'health', 'initial': 20000, 'capacity': 20000}}, 'spatial': {},
            'selection_state': {'side': 0, 'motion': 1, 'category': 1}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}}],
        'scenarioDraft': {'id': 'scene/c9/native_road_infection', 'ruleset': 'ruleset/ark_standard', 'map': plan,
            'initialEntities': [{'definition': 'unit/c9/infection/probe', 'instanceAlias': 'probe', 'position': {'row': row, 'col': col}}]}}
    module = ROOT / 'packages/campaign/chapter08_consumers/environment/infection.module.v3.json'
    reg = infection_providers(); program = Compiler(providers=reg).compile(package, packages=[str(module)])
    sim = Engine.create(program, providers=reg); sim.advance(29)
    path = tmp_path / 'native_infection.checkpoint.json'; path.write_text(json.dumps(sim.checkpoint()), encoding='utf8')
    resumed = Engine.restore(program, json.loads(path.read_bytes()), providers=reg); sim.advance(32); resumed.advance(32)
    assert sim.checkpoint() == resumed.checkpoint() == replay(program, sim.export_replay(), providers=reg).checkpoint()
    assert [(e['time'], e['payload']['amount'], e['payload']['source']) for e in sim.session.events if e['type'] == 'damage.accepted'] == [(30, 180, None), (60, 180, None)]
    assert sim.ctx.resources.current('probe', 'hp') == 19640
