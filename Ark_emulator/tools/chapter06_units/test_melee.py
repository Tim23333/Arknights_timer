"""Independent actual source-frame/combat/route witnesses for C6 exact shield and Frozen-conditional swordsman."""
import hashlib
import json
from pathlib import Path
import pytest
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound
from tools.chapter06.cold.policies import providers
from ark_sim.domains.selection import DEFAULT_STATE
COLDMODULE=Path(__file__).resolve().parents[2]/'packages/campaign/chapter06_cold/model.json'

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT/'packages/campaign/chapter06_units/melee.model.json'
PIN = '7417d5342a7affec7d872715bb810c01dc65422dcd30c41064d33ec33a776f31'
CASES = [('enemy_1006_shield_2',10000,600,1000,14,78,500),
         ('enemy_1064_snsbr',3400,360,100,12,60,260)]
PARAM = pytest.mark.parametrize('native,maxhp,atk,defense,frame,interval,outgoing', CASES)


def fixture_package(native, *, initial_hp=None, route=True, objectives=False):
    assert hashlib.sha256(MODULE.read_bytes()).hexdigest() == PIN
    p = json.loads(MODULE.read_bytes())
    unit = next(u for u in p['entities'] if u['metadata']['native_reference']['id'] == native)
    enemy = {'definition': unit['id'], 'instanceAlias': 'enemy', 'position': {'row': 0, 'col': 0}}
    if initial_hp is not None: enemy['components'] = {'resources': {'hp': {'initial': initial_hp}}}
    if route: enemy['route'] = {'motionMode': 'WALK', 'startPosition': {'row': 0, 'col': 0},
        'endPosition': {'row': 0, 'col': 3}, 'checkpoints': []}
    p['entities'].append({'id': 'unit/test/plain_blocker', 'kind': 'entity', 'tags': ['player', 'ground'],
        'components': {'attributes': {'base': {'max_hp': 10000, 'atk': 1250, 'def': 100, 'mres': 0, 'block_count': 1}},
            'resources': {'hp': {'initial': 10000, 'capacity': 10000, 'role': 'health'}}, 'spatial': {},
            'deployable': {'base_cost': 7, 'capacity': 1, 'cooldown_seconds': 0, 'terrain': 'ground'},
            'lifecycle': {'policy': 'policy/ark_lifecycle'}, 'abilities': ['ability/test/plain_damage']}})
    p['selectors'].append({'id': 'selector/test/plain_enemy', 'kind': 'selector', 'region': {'type': 'all'},
        'filters': [{'tag': 'enemy'}, {'state': 'alive'}], 'limit': 1})
    p['abilities'].append({'id': 'ability/test/plain_damage', 'kind': 'ability', 'selector': 'selector/test/plain_enemy',
        'activation': {'mode': 'manual'}, 'timeline': [{'at': 0, 'effect': {'op': 'damage', 'damage_type': 'physical', 'scale': 1}}]})
    p['scenarioDraft'] = {'id': 'scene/ch6/closed_melee_author', 'ruleset': 'ruleset/ark_standard',
        'objectives': {'type': 'waves', 'life_resource': 'life'} if objectives else {},
        'map': {'rows': 1, 'cols': 5}, 'resources': {'dp': {'initial': 20, 'capacity': 99}, 'life': {'initial': 99999, 'capacity': 99999}},
        'roster': ['unit/test/plain_blocker'], 'initialEntities': [enemy]}
    return p


def fixture(native, **kwargs): return Engine.create(Compiler(providers=providers()).compile(fixture_package(native, **kwargs),packages=[COLDMODULE]), seed=6616, providers=providers())
def hp(s, who='enemy'): return s.ctx.resources.current(who, 'hp')
def deploy(s, at=0, alias='blocker'): s.submit({'action': 'deploy', 'definition': 'unit/test/plain_blocker', 'alias': alias, 'position': {'row': 0, 'col': 0}}, at=at)
def damage(s, at=5): s.submit({'action': 'skill', 'source': 'blocker', 'ability': 'ability/test/plain_damage'}, at=at)


@PARAM
def test_exact_source_stats_and_no_recovery_driver(native, maxhp, atk, defense, frame, interval, outgoing):
    assert implementation_digest() == '4ef955c5d5a7628382fc3d15003bb0a30c749832d210ca50897355568ec8d329'
    p = fixture_package(native); u = next(u for u in p['entities'] if u.get('metadata', {}).get('native_reference', {}).get('id') == native)
    a = u['components']['attributes']['base']; spec = u['components']['resources']['hp']
    assert (a['max_hp'], a['atk'], a['def'], a['attack_interval']*30) == (maxhp, atk, defense, interval)
    assert spec['initial'] == maxhp and not any(k in spec for k in ('recovery', 'recovery_rate', 'recovery_rule'))
    source = json.loads((ROOT/'packages/campaign/chapter06_sources/native.reference.json').read_bytes())
    v = next(v for v in source['variants'].values() if v['native_enemy']['native_id'] == native)
    assert v['native_enemy']['resolved']['attributes']['hpRecoveryPerSec'] == 0
    assert v['modes'][0]['nodes']['_combat']['animation_binding']['events'][0]['frame'] == frame


@PARAM
def test_actual_block_and_golden_two_hits_with_seven_dp_cost(native, maxhp, atk, defense, frame, interval, outgoing):
    s = fixture(native); deploy(s); s.session.advance(2)
    assert s.ctx.spatial.blocked_by('enemy') == s.session.world.resolve('blocker')
    assert s.ctx.resources.current('system/battle', 'dp') == 13
    s.session.advance(frame-1)
    assert [e for e in s.session.events if e['type'] == 'damage.accepted'] == []
    s.session.advance(interval+1)
    events = [e for e in s.session.events if e['type'] == 'damage.accepted']
    assert [(e['time'], e['payload']['amount']) for e in events] == [(frame+1, outgoing), (frame+1+interval, outgoing)]
    assert hp(s, 'blocker') == 10000-2*outgoing and hp(s) == maxhp


@PARAM
def test_public_hit_remains_lost_hp_no_phantom_zero_recovery(native, maxhp, atk, defense, frame, interval, outgoing):
    s = fixture(native); deploy(s); damage(s)
    s.session.advance(121)
    enemy = s.session.world.resolve('enemy')
    incoming = [e for e in s.session.events if e['type'] == 'damage.accepted' and e['payload']['target'] == enemy]
    assert [(e['time'], e['payload']['amount']) for e in incoming] == [(5,1250-defense)]
    assert hp(s) == maxhp-(1250-defense)
    assert not [e for e in s.session.events if e['type'] == 'resource.changed' and e['payload']['target'] == enemy
                and e['payload']['resource'] == 'hp' and e['payload']['delta'] > 0]


@PARAM
def test_rejected_duplicate_deployment_has_no_second_cost(native, maxhp, atk, defense, frame, interval, outgoing):
    s = fixture(native); deploy(s); deploy(s, at=1, alias='second'); s.session.advance(2)
    assert s.ctx.resources.current('system/battle', 'dp') == 13
    assert len([e for e in s.session.events if e['type'] == 'command.rejected']) == 1
    assert len([e for e in s.session.events if e['type'] == 'entity.deployed']) == 1


@PARAM
def test_actual_hp_death_cancels_windup_no_resurrection(native, maxhp, atk, defense, frame, interval, outgoing):
    s = fixture(native, initial_hp=200); deploy(s); damage(s)
    s.session.advance(6)
    assert hp(s) == 0 and not s.ctx.alive('enemy') and not s.ctx.state()['finished']
    s.session.advance(120)
    assert hp(s) == 0 and hp(s, 'blocker') == 10000
    assert len([e for e in s.session.events if e['type'] == 'entity.died']) == 1


@PARAM
def test_source_route_reaches_actual_exit_and_only_base_loses_one(native, maxhp, atk, defense, frame, interval, outgoing):
    s = fixture(native, objectives=True)
    s.session.advance(10)
    assert s.ctx.get('enemy', ('spatial', 'position'))['col'] > 0 and hp(s) == maxhp
    s.session.advance(230)
    assert not s.ctx.alive('enemy') and s.ctx.get('enemy', ('runtime', 'state')) == 'exited'
    assert s.ctx.state()['leaks'] == 1 and s.ctx.state()['kills'] == 0 and s.ctx.state()['finished']
    assert s.ctx.resources.current('system/battle', 'life') == 99998 and hp(s) == maxhp
    assert s.snapshot() == replay(s.program, s.export_replay(),providers=providers()).snapshot()


@PARAM
def test_withdrawal_releases_actual_block_and_walker_resumes(native, maxhp, atk, defense, frame, interval, outgoing):
    s = fixture(native); deploy(s); s.submit({'action': 'withdraw', 'source': 'blocker'}, at=5)
    s.session.advance(6)
    assert s.ctx.spatial.blocked_by('enemy') is None and not s.ctx.alive('blocker')
    s.session.advance(24)
    assert s.ctx.get('enemy', ('spatial', 'position'))['col'] > 0


@PARAM
@pytest.mark.parametrize('dying', [False, True])
def test_real_saved_cp_and_from_start_public_replay_preserve_cost_hits_and_death(native, maxhp, atk, defense, frame, interval, outgoing, dying, tmp_path):
    s = fixture(native, initial_hp=200 if dying else None); deploy(s); damage(s)
    s.session.advance(2)
    path = tmp_path/'actual.plain.json'; pin = write_ordered(path, s.checkpoint())
    restored = Engine.restore(s.program, load_bound(path, pin),providers=providers())
    s.session.advance(119); restored.session.advance(119)
    assert s.snapshot() == restored.snapshot() == replay(s.program, s.export_replay(),providers=providers()).snapshot()
    assert hp(s) == (0 if dying else maxhp-(1250-defense))
    assert s.ctx.resources.current('system/battle', 'dp') == 13


def cold_fixture(native='enemy_1064_snsbr',immune=()):
    p=fixture_package(native)
    blocker=next(u for u in p['entities'] if u['id']=='unit/test/plain_blocker')
    blocker['tags'].append('cold_receiver')
    blocker['components']['selection_state']={'side':0,'motion':1,'category':1,'unit_type':1,'abnormal_immunes':list(immune)}
    p['entities'].append({'id':'unit/test/c6/coldcaster','kind':'entity','tags':['test_caster'],'components':{'attributes':{'base':{'max_hp':10,'atk':1}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},'spatial':{},'abilities':['ability/ch6/cold/apply5','ability/ch6/cold/apply10'],'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']['initialEntities'].append({'definition':'unit/test/c6/coldcaster','instanceAlias':'coldcaster','position':{'row':0,'col':4}})
    return p


def submit_cold(s):
    for tick in (20,21):s.submit({'action':'skill','source':'coldcaster','ability':'ability/ch6/cold/apply5'},at=tick)


def test_real_snsbr_conditional_normal_frozen_expired_packets_and_unchanged_atk():
    s=Engine.create(Compiler(providers=providers()).compile(cold_fixture(),packages=[COLDMODULE]),seed=6616,providers=providers())
    deploy(s);submit_cold(s);s.session.advance(194)
    assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(13,260),(73,440),(133,440),(193,260)]
    assert s.ctx.attributes.value('enemy','atk')==360
    assert hp(s,'blocker')==8600 and 16 not in s.ctx.spatial.selection_state('blocker',DEFAULT_STATE)['abnormal_flags']


@pytest.mark.parametrize('native,immune,expected', [('enemy_1064_snsbr',[16],[(13,260),(73,260),(133,260),(193,260)]),('enemy_1006_shield_2',[],[(15,500),(93,500),(171,500)])])
def test_immune_or_plain_enemy_never_inherits_conditional_buff(native,immune,expected):
    s=Engine.create(Compiler(providers=providers()).compile(cold_fixture(native,immune),packages=[COLDMODULE]),seed=6616,providers=providers())
    deploy(s);submit_cold(s);s.session.advance(194)
    assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==expected


def test_source_passive_frozen_packets_disk_cp_and_head_replay(tmp_path):
    s=Engine.create(Compiler(providers=providers()).compile(cold_fixture(),packages=[COLDMODULE]),seed=6616,providers=providers())
    deploy(s);submit_cold(s);s.session.advance(22)
    assert 16 in s.ctx.spatial.selection_state('blocker',DEFAULT_STATE)['abnormal_flags']
    p=tmp_path/'actual.snsbr.frozen.json';pin=write_ordered(p,s.checkpoint())
    restored=Engine.restore(s.program,load_bound(p,pin),providers=providers())
    s.session.advance(172);restored.session.advance(172)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
    assert hp(s,'blocker')==8600


@PARAM
def test_public_arts_hit_consumes_exact_source_res_zero_independent_of_defense(native,maxhp,atk,defense,frame,interval,outgoing):
    p=fixture_package(native)
    ability=next(a for a in p['abilities'] if a['id']=='ability/test/plain_damage')
    ability['timeline'][0]['effect']['damage_type']='arts'
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLDMODULE]),seed=6616,providers=providers())
    deploy(s);damage(s);s.session.advance(6)
    assert s.ctx.attributes.value('enemy','mres')==0
    assert hp(s)==maxhp-1250
    assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(5,1250)]
