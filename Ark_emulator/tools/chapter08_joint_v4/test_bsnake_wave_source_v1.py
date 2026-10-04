"""Literal native Default tracking survives realHP0 while originalbirths finish."""
import json
from copy import deepcopy
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.chapter08_joint_v4.build_bsnake_wave_source_v1 import OUT, build, BASE, TRACK, RELEASE, BGM
from tools.chapter08_joint_v4.build_bsnake_partial_join_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered, load_bound


def package():
    p = json.loads(OUT.read_bytes())
    loop = json.loads((BASE.parent / 'flame/loop.profile.v3.json').read_bytes())
    p['definitions'] += [
        {'id': 'unit/ch8/flame/level1', 'kind': 'entity', 'components': {'spatial': {}}},
        {'id': 'unit/wavesource/other', 'kind': 'entity', 'tags': ['enemy'], 'components': {
            'attributes': {'base': {'max_hp': 1000}}, 'resources': {'hp': {'initial': 1000, 'capacity': 1000, 'role': 'health'}},
            'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
        {'id': 'unit/wavesource/director', 'kind': 'entity', 'components': {'spatial': {}, 'abilities': ['ability/wavesource/kill']}},
        {'id': 'selector/wavesource/boss', 'kind': 'selector', 'region': {'type': 'all'}, 'filters': [{'tag': 'boss'}]},
        {'id': 'ability/wavesource/kill', 'kind': 'ability', 'selector': 'selector/wavesource/boss',
         'activation': {'mode': 'manual', 'on_start': [{'op': 'instant_kill', 'parameters': {'cause': 'source_first_wave', 'skip_rebirth': False}}]},
         'timeline': []},
    ]
    def spawn(unit, alias, delay=0):
        return {'kind': 'spawn', 'delay_seconds': delay, 'spawn': {'definition': unit, 'instanceAlias': alias,
                'position': {'row': 4, 'col': 10}}, 'blocks_wave': True}
    p['scenarioDraft'] = {'id': 'scene/bsnake/native_wave_source', 'ruleset': 'ruleset/ark_standard',
                          'map': {'rows': 9, 'cols': 15}, 'branches': loop['runtime_branch'], 'objectives': {},
                          'initialEntities': deepcopy(loop['initial_entities']) + [
                              {'definition': 'unit/wavesource/director', 'instanceAlias': 'director', 'position': {'row': 0, 'col': 0}}],
                          'timeline': {'policy': 'managed_clear', 'negative_timeout_policy': 'wait_for_clear', 'waves': [
                              {'post_delay_seconds': 3 / 30, 'max_wait_seconds': -1, 'fragments': [{'actions': [
                                  spawn('unit/ch8/bsnake/cadb87696bef4de2', 'boss'), spawn('unit/wavesource/other', 'old_other', 20 / 30)]}]},
                              {'pre_delay_seconds': 5 / 30, 'max_wait_seconds': -1, 'fragments': [{'actions': [
                                  spawn('unit/wavesource/other', 'next_other')]}]},
                          ]}}
    return p


def test_native_hierarchy_paths_and_literal_parameters_rebuild():
    p = json.loads(OUT.read_bytes())
    assert p == build()
    assert p['manifest']['metadata']['native_wave_talent_paths']['track'].endswith('/Default/Talent/TrackAtNextWave')
    assert p['manifest']['metadata']['native_wave_talent_paths']['release'].endswith('/Reborn/Talent/ReleaseWave')


def test_actual_source_buff_firstHP0_tracks_realBoss_and_keeps_latebirths_CP15_head(tmp_path):
    reg = providers()
    s = Engine.create(Compiler(providers=reg).compile(package()), providers=reg, seed=82771)
    s.submit({'action': 'skill', 'source': 'director', 'ability': 'ability/wavesource/kill'}, at=7)
    s.advance(15)
    boss = s.session.world.resolve('boss')
    assert s.ctx.alive(boss) and not s.ctx.active(boss) and s.ctx.resources.current(boss, 'hp') == 0
    state = s.ctx.state()['timeline']
    assert state['tracking_requests']['0']['source'] == boss and state['tracking_requests']['0']['status'] == 'pending'
    path = tmp_path / 'nativewave15.cp.json'
    pin = write_ordered(path, s.checkpoint())
    r = Engine.restore(s.program, load_bound(path, pin), providers=reg)
    s.advance(165)
    r.advance(165)
    h = replay(s.program, s.export_replay(), providers=reg)
    assert s.checkpoint() == r.checkpoint() == h.checkpoint()
    assert list(s.session.events) == list(r.session.events) == list(h.session.events)
    state = s.ctx.state()['timeline']
    assert state['members'][str(boss)]['wave'] == 1
    assert state['members'][str(s.session.world.resolve('old_other'))]['wave'] == 0
    assert state['members'][str(s.session.world.resolve('next_other'))]['wave'] == 1
    assert [event['time'] for event in s.session.events if event['type'] == 'timeline.source_transferred'] == [23]
    assert s.ctx.resources.current(boss, 'hp') == 37500 and s.ctx.resources.current(boss, 'mode') == 2
    removed = [event['payload']['buff'] for event in s.session.events if event['type'] == 'buff.removed']
    assert TRACK in removed and BGM in removed and RELEASE not in removed
    assert len([event for event in s.session.events if event['type'] == 'source.bsnake.bgm.observed']) == 1
