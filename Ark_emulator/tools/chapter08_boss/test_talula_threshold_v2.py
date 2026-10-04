"""Actual original50000HP boundary and once-only source rage state."""
import json

from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter08_boss.build_talula_threshold_v2 import OUT, RAGE, UNIT, build, sha


def package():
    assert sha(OUT) == '6f4c51ae8ec319d31423a50879da672e1368308a5097793d9034e45120e3abcf'
    p = json.loads(OUT.read_bytes())
    p['scenarioDraft'] = {'id': 'scene/ch8/talula/threshold_author', 'ruleset': 'ruleset/ark_standard', 'seed': 81617,
        'map': {'rows': 1, 'cols': 2}, 'initialEntities': [{'definition': UNIT, 'instanceAlias': 'boss', 'position': {'row': 0, 'col': 0}},
            {'definition': 'unit/ch8/threshold/author', 'instanceAlias': 'author', 'position': {'row': 0, 'col': 1}}]}
    p['selectors'] = [{'id': 'selector/ch8/threshold/boss', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'boss'}]}]
    effects = {'one': {'op': 'modify_resource', 'resource': 'hp', 'delta': -1},
        'above': {'op': 'modify_resource', 'resource': 'hp', 'delta': -24999},
        'heal': {'op': 'modify_resource', 'resource': 'hp', 'delta': 10000},
        'kill': {'op': 'damage', 'damage_type': 'true', 'scale': 1, 'damage_flags': {'source_attack_type': 'NONE', 'ignore_for_sp': True}}}
    p['abilities'] = [{'id': 'ability/ch8/threshold/'+name, 'kind': 'ability', 'selector': 'selector/ch8/threshold/boss',
        'activation': {'mode': 'manual'}, 'timeline': [{'at': 0, 'effect': effect}]} for name, effect in effects.items()]
    p['entities'].append({'id': 'unit/ch8/threshold/author', 'kind': 'entity', 'tags': ['player'], 'components': {
        'attributes': {'base': {'atk': 50000, 'max_hp': 100}}, 'resources': {'hp': {'initial': 100, 'capacity': 100, 'role': 'health'}},
        'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}, 'abilities': [a['id'] for a in p['abilities']]},
        'metadata': {'isolated_author_actor': True, 'not_fixed_roster_or_original_stage': True}})
    return p


def command(s, name, at):
    s.submit({'action': 'skill', 'source': 'author', 'ability': 'ability/ch8/threshold/'+name}, at=at)


def proof(commands, tmp_path, split=5, end=12):
    p = package()
    program = Compiler().compile(p)
    s = Engine.create(program)
    for name, at in commands:
        command(s, name, at)
    s.session.advance(split)
    cp = tmp_path/'actual.cp.json'
    h = write_ordered(cp, s.checkpoint())
    r = Engine.restore(program, load_bound(cp, h))
    s.session.advance(end-split)
    r.session.advance(end-split)
    head = replay(program, s.export_replay())
    assert s.snapshot() == r.snapshot() == head.snapshot()
    assert list(s.session.events) == list(r.session.events) == list(head.session.events)
    return s


def test_source_exact_rebuild_and_original_stats_not_false_DB50():
    assert json.loads(OUT.read_bytes()) == build()
    s = Engine.create(Compiler().compile(package()))
    assert s.ctx.resources.current('boss', 'hp') == 50000
    assert s.ctx.resources.current('boss', 'mode') == 0
    assert s.ctx.entity('boss')['components']['attributes']['base']['def'] == 700


def test_above_half25001_does_not_trigger(tmp_path):
    s = proof([('above', 2)], tmp_path)
    assert s.ctx.resources.current('boss', 'hp') == 25001
    assert s.ctx.resources.current('boss', 'mode') == 0
    assert not any(e['type'] == 'behavior.transition' for e in s.session.events)
    assert not s.ctx.get('boss', ('buffs', 'instances'), [])


def test_exact_half25000_triggers_one_real_buff_DEF1400_RES90(tmp_path):
    s = proof([('above', 2), ('one', 4)], tmp_path)
    assert s.ctx.resources.current('boss', 'hp') == 25000
    assert s.ctx.resources.current('boss', 'mode') == 1
    transitions = [e for e in s.session.events if e['type'] == 'behavior.transition']
    assert len(transitions) == 1 and transitions[0]['payload']['to'] == 'half'
    buffs = s.ctx.get('boss', ('buffs', 'instances'), [])
    assert len(buffs) == 1 and buffs[0]['definition'] == RAGE and buffs[0]['expires_at'] is None
    assert s.ctx.attributes.value('boss', 'def') == 1400
    assert s.ctx.attributes.value('boss', 'mres') == 90


def test_heal35000_keeps_once_only_rage_then_second_cross_no_reapply(tmp_path):
    s = proof([('above', 2), ('one', 4), ('heal', 6), ('above', 8)], tmp_path)
    assert s.ctx.resources.current('boss', 'hp') == 10001
    assert s.ctx.resources.current('boss', 'mode') == 1
    assert len([e for e in s.session.events if e['type'] == 'behavior.transition']) == 1
    assert len([e for e in s.session.events if e['type'] == 'buff.applied']) == 1
    assert s.ctx.attributes.value('boss', 'def') == 1400


def test_real_lethal50000_damage_does_not_create_halfstate_after_death(tmp_path):
    s = proof([('kill', 2)], tmp_path, split=1, end=6)
    assert s.ctx.resources.current('boss', 'hp') == 0
    assert not s.ctx.alive('boss')
    assert not any(e['type'] == 'behavior.transition' for e in s.session.events)
    hits = [e for e in s.session.events if e['type'] == 'damage.accepted']
    assert len(hits) == 1 and hits[0]['payload']['amount'] == 50000
