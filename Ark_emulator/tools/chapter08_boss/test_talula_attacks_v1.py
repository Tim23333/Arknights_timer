"""Real two-mode attacks: native40PURE and30 arts projectile, shared135cycle."""
import json
import pytest

from ark_sim import Compiler, Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter08_boss.build_talula_attacks_v1 import OUT, build, sha
from tools.chapter08_boss.talula_policies_v1 import providers


def package(blocked=False, half=False):
    assert sha(OUT) == '31ed589aa6650fd62ead713ace25480744ceeabbc7cd6ec393e26ca876800b40'
    p = json.loads(OUT.read_bytes())
    unit = p['entities'][0]['id']
    p['entities'].append({'id': 'unit/ch8/talula/author', 'kind': 'entity', 'tags': ['player'], 'components': {
        'attributes': {'base': {'max_hp': 10000, 'atk': 0, 'def': 811, 'mres': 27, 'block_count': 1}},
        'resources': {'hp': {'initial': 10000, 'capacity': 10000, 'role': 'health'}},
        'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1}, 'spatial': {},
        'deployable': {'base_cost': 7, 'capacity': 1, 'terrain': 'ground', 'cooldown_seconds': 0},
        'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    source = {'definition': unit, 'instanceAlias': 'boss', 'position': {'row': 1, 'col': 1}}
    if blocked:
        source['route'] = {'motionMode': 'WALK', 'startPosition': {'row': 1, 'col': 1}, 'endPosition': {'row': 1, 'col': 4}, 'checkpoints': []}
    p['scenarioDraft'] = {'id': 'scene/ch8/talula/attacks_author', 'ruleset': 'ruleset/ark_standard', 'seed': 81617,
        'map': {'rows': 3, 'cols': 5}, 'resources': {'dp': {'initial': 20, 'capacity': 99}},
        'roster': ['unit/ch8/talula/author'], 'initialEntities': [source]}
    if not blocked:
        p['scenarioDraft']['initialEntities'].append({'definition': 'unit/ch8/talula/author', 'instanceAlias': 'target', 'position': {'row': 1, 'col': 2}})
    if half:
        p['selectors'].append({'id': 'selector/ch8/talula/authorboss', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'boss'}]})
        p['scenarioDraft']['scheduledEffects'] = [{'at': 0, 'effect': {'op': 'modify_resource', 'resource': 'hp', 'value': 25000, 'selector': 'selector/ch8/talula/authorboss'}}]
    return p


def simulate(p, tmp_path, split, end, blocked=False, commands=()):
    reg = providers()
    program = Compiler(providers=reg).compile(p)
    s = Engine.create(program, providers=reg)
    if blocked:
        s.submit({'action': 'deploy', 'definition': 'unit/ch8/talula/author', 'alias': 'target', 'position': {'row': 1, 'col': 1}}, at=0)
    for command, at in commands:
        s.submit(command, at=at)
    s.advance(split)
    cp = tmp_path/'actual.cp.json'
    h = write_ordered(cp, s.checkpoint())
    r = Engine.restore(program, load_bound(cp, h), providers=reg)
    s.advance(end-split)
    r.advance(end-split)
    head = replay(program, s.export_replay(), providers=reg)
    assert s.snapshot() == r.snapshot() == head.snapshot()
    assert list(s.session.events) == list(r.session.events) == list(head.session.events)
    return s


def hits(s):
    return [e for e in s.session.events if e['type'] == 'damage.accepted']


def test_exact_rebuild_and_defined_source_immunities():
    assert json.loads(OUT.read_bytes()) == build()
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(package()), providers=reg)
    state = s.ctx.spatial.selection_state('boss', DEFAULT_STATE)
    assert state['abnormal_immunes'] == [0,12,16,25] and state['abnormal_combo_immunes'] == [0]
    assert s.ctx.resources.current('boss', 'hp') == 50000


@pytest.mark.parametrize('half', [False, True])
def test_actual_blocked40frame135cycle_TRUE1500_despite_DEF811_RES27(half, tmp_path):
    s = simulate(package(True, half), tmp_path, 20, 185, blocked=True)
    assert [(e['time'], e['payload']['amount']) for e in hits(s)] == [(41,1500),(176,1500)]
    assert all(e['payload']['ability'].endswith('/combat') for e in hits(s))
    assert s.ctx.resources.current('target', 'hp') == 7000
    assert s.ctx.resources.current('system/battle', 'dp') == 13
    assert s.ctx.resources.current('boss', 'mode') == int(half)


@pytest.mark.parametrize('half', [False, True])
def test_actual_unblocked30launch_homing10_hit33_arts438_cycle135(half, tmp_path):
    s = simulate(package(False, half), tmp_path, 31, 175)
    expected = 1500*.4000000059604645*.73
    assert [e['time'] for e in hits(s)] == [33,168]
    assert all(e['payload']['amount'] == pytest.approx(expected) for e in hits(s))
    assert all(e['payload']['ability'].endswith('/attack') for e in hits(s))
    assert [e['time'] for e in s.session.events if e['type'] == 'projectile.launched'] == [30,165]


def test_typed_range_free_camouflage_side_category_reject():
    for field, value in [('target_free',True),('camouflage',True),('side',1),('category',4)]:
        p = package()
        p['entities'][-1]['components']['selection_state'][field] = value
        reg = providers()
        s = Engine.create(Compiler(providers=reg).compile(p), providers=reg)
        s.advance(40)
        assert not hits(s)
    p = package()
    p['scenarioDraft']['initialEntities'][1]['position']['col'] = 3.500001
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(p), providers=reg)
    s.advance(40)
    assert not hits(s)


def test_current_RES_before_impact_27plus16_actual342(tmp_path):
    p = package()
    p['buffs'].append({'id': 'buff/ch8/talula/authorres', 'kind': 'buff', 'duration_seconds': 5,
        'modifiers': [{'attribute': 'mres', 'layer': 'flat', 'value': 16}]})
    p['selectors'].append({'id': 'selector/ch8/talula/authorplayer', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'player'}]})
    p['scenarioDraft']['scheduledEffects'] = [{'at': 31, 'effect': {'op': 'apply_buff', 'buff': 'buff/ch8/talula/authorres', 'selector': 'selector/ch8/talula/authorplayer'}}]
    s = simulate(p, tmp_path, 30, 40)
    assert len(hits(s)) == 1 and hits(s)[0]['time'] == 33
    assert hits(s)[0]['payload']['amount'] == pytest.approx(1500*.4000000059604645*.57)


def test_real_source_ASPD2_15launch18impact_and_shared68cycle(tmp_path):
    p = package()
    p['buffs'].append({'id': 'buff/ch8/talula/authorspeed', 'kind': 'buff', 'duration_seconds': 5,
        'modifiers': [{'attribute': 'attack_speed_ratio', 'layer': 'flat', 'value': 1}]})
    p['selectors'].append({'id': 'selector/ch8/talula/authorboss', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'boss'}]})
    p['scenarioDraft']['scheduledEffects'] = [{'at': 0, 'effect': {'op': 'apply_buff', 'buff': 'buff/ch8/talula/authorspeed', 'selector': 'selector/ch8/talula/authorboss'}}]
    s = simulate(p, tmp_path, 16, 95)
    assert [e['time'] for e in hits(s)] == [18,86]
    assert [e['time'] for e in s.session.events if e['type'] == 'projectile.launched'] == [15,83]
