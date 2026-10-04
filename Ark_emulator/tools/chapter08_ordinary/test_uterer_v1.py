"""Actual source frames, live arithmetic, blocking, retirement and ordered restore."""
import json
from pathlib import Path

from ark_sim import Compiler, Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter08_ordinary.build_uterer_v1 import ROOT, OUT, UNIT, ABILITY, build, sha

MODULE_SHA = '97f67cd2aebf8e6d2ea01f1b5ff55ff8ff2ffaf1208634807be218f1149e5c54'


def package():
    assert sha(OUT) == MODULE_SHA
    p = json.loads(OUT.read_bytes())
    p['entities'].append({'id': 'unit/ch8/author/blocker', 'kind': 'entity', 'tags': ['player', 'ground'], 'components': {
        'attributes': {'base': {'max_hp': 10000, 'atk': 0, 'def': 137, 'mres': 27, 'block_count': 1}},
        'resources': {'hp': {'initial': 10000, 'capacity': 10000, 'role': 'health'}},
        'selection_state': {'side': 0, 'motion': 1, 'category': 1, 'unit_type': 1}, 'spatial': {},
        'deployable': {'base_cost': 7, 'capacity': 1, 'cooldown_seconds': 0, 'terrain': 'ground'},
        'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    p['scenarioDraft'] = {'id': 'scene/ch8/uterer/author', 'ruleset': 'ruleset/ark_standard', 'seed': 81617,
        'map': {'rows': 1, 'cols': 5}, 'resources': {'dp': {'initial': 20, 'capacity': 99}},
        'roster': ['unit/ch8/author/blocker'], 'initialEntities': [{'definition': UNIT, 'instanceAlias': 'source',
            'position': {'row': 0, 'col': 0}, 'route': {'motionMode': 'WALK', 'startPosition': {'row': 0, 'col': 0},
                'endPosition': {'row': 0, 'col': 4}, 'checkpoints': []}}]}
    return p


def deploy(s):
    s.submit({'action': 'deploy', 'definition': 'unit/ch8/author/blocker', 'alias': 'blocker', 'position': {'row': 0, 'col': 0}}, at=0)


def hits(s):
    return [e for e in s.session.events if e['type'] == 'damage.accepted']


def starts(s):
    return [e for e in s.session.events if e['type'] == 'ability.started' and e['payload']['ability'] == ABILITY]


def roundtrip(p, tmp_path, split, end, *, deploying=True):
    program = Compiler().compile(p)
    s = Engine.create(program)
    if deploying:
        deploy(s)
    s.session.advance(split)
    path = tmp_path/'actual.cp.json'
    h = write_ordered(path, s.checkpoint())
    r = Engine.restore(program, load_bound(path, h))
    s.session.advance(end-split)
    r.session.advance(end-split)
    head = replay(program, s.export_replay())
    assert s.snapshot() == r.snapshot() == head.snapshot()
    assert list(s.session.events) == list(r.session.events) == list(head.session.events)
    return s


def test_exact_source_rebuild_and_no_copied_silence_immunity():
    p = json.loads(OUT.read_bytes())
    assert p == build()
    s = Engine.create(Compiler().compile(package()))
    b = s.ctx.entity('source')['components']['attributes']['base']
    assert (b['max_hp'], b['atk'], b['def'], b['mres'], b['move_speed'], b['attack_interval']) == (3500, 380, 100, 20, 1.7, 1.5)
    assert 'sp' not in s.ctx.entity('source')['components']['resources']
    assert s.ctx.spatial.selection_state('source', DEFAULT_STATE)['abnormal_immunes'] == []
    assert p['manifest']['metadata']['reference_policy']['undefined_DB_defaults_are_not_defined_source_values'] is True


def test_blocked12frame45cycle_real243_damage_DP7_CP_head(tmp_path):
    s = roundtrip(package(), tmp_path, 7, 65)
    assert s.ctx.spatial.blocked_by('source') == s.session.world.resolve('blocker')
    assert s.ctx.resources.current('system/battle', 'dp') == 13
    assert [e['time'] for e in hits(s)] == [13, 58]
    assert [e['payload']['amount'] for e in hits(s)] == [243, 243]
    assert [e['time'] for e in starts(s)] == [1, 46]
    assert s.ctx.resources.current('blocker', 'hp') == 9514


def test_public_apply_buff_source_ASPD3_actual4frame15cycle(tmp_path):
    p = package()
    p['buffs'] = [{'id': 'buff/ch8/author/speed3', 'kind': 'buff', 'duration_seconds': 5,
        'modifiers': [{'attribute': 'attack_speed_ratio', 'layer': 'flat', 'value': 2}]}]
    p['selectors'].append({'id': 'selector/ch8/author/source', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'enemy'}]})
    p['scenarioDraft']['scheduledEffects'] = [{'at': 0, 'effect': {'op': 'apply_buff', 'buff': 'buff/ch8/author/speed3', 'selector': 'selector/ch8/author/source'}}]
    s = roundtrip(p, tmp_path, 3, 25)
    assert [e['time'] for e in hits(s)] == [5, 20]
    assert [e['time'] for e in starts(s)] == [1, 16]
    assert [e['payload']['amount'] for e in hits(s)] == [243, 243]


def test_current_target_DEF_at_hit_137plus100_real143(tmp_path):
    p = package()
    p['buffs'] = [{'id': 'buff/ch8/author/def100', 'kind': 'buff', 'duration_seconds': 5,
        'modifiers': [{'attribute': 'def', 'layer': 'flat', 'value': 100}]}]
    p['selectors'].append({'id': 'selector/ch8/author/player', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'player'}]})
    p['scenarioDraft']['scheduledEffects'] = [{'at': 8, 'effect': {'op': 'apply_buff', 'buff': 'buff/ch8/author/def100', 'selector': 'selector/ch8/author/player'}}]
    s = roundtrip(p, tmp_path, 6, 20)
    assert len(hits(s)) == 1 and hits(s)[0]['time'] == 13 and hits(s)[0]['payload']['amount'] == 143


def test_withdraw_current_blocker_before_hit_no_damage_then_route_exit(tmp_path):
    p = package()
    program = Compiler().compile(p)
    s = Engine.create(program)
    deploy(s)
    s.submit({'action': 'withdraw', 'source': 'blocker'}, at=8)
    s.session.advance(6)
    cp = tmp_path/'withdraw.cp.json'
    h = write_ordered(cp, s.checkpoint())
    r = Engine.restore(program, load_bound(cp, h))
    s.session.advance(110)
    r.session.advance(110)
    head = replay(program, s.export_replay())
    assert s.snapshot() == r.snapshot() == head.snapshot()
    assert list(s.session.events) == list(r.session.events) == list(head.session.events)
    assert not hits(s)
    assert any(e['type'] == 'route.exited' for e in s.session.events)


def test_source_death_midcast_cancels_payload_without_immortality(tmp_path):
    p = package()
    p['selectors'].append({'id': 'selector/ch8/author/source', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'enemy'}]})
    p['scenarioDraft']['scheduledEffects'] = [{'at': 8, 'effect': {'op': 'damage', 'selector': 'selector/ch8/author/source',
        'damage_type': 'pure', 'amount': 3500, 'damage_flags': {'ignore_for_sp': True}}}]
    s = roundtrip(p, tmp_path, 6, 25)
    assert s.ctx.resources.current('source', 'hp') == 0
    assert not any(e['payload'].get('source') == s.session.world.resolve('source') for e in hits(s))
    assert any(e['type'] == 'entity.died' for e in s.session.events)
