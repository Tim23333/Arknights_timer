"""Public target deployment drives exact native normal/SP/Cold/Ready probes."""
from pathlib import Path
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_units.snmage.build_module import ROOT,OUT,COLD,CORE,UID,NORMAL,SKILL,READY,SELECT
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def package(*,initial_sp=0,immune=(),second=False,repeat=False):
    p=json.loads((OUT/'model.json').read_bytes());p['entities'][0]['components']['resources']['sp']['initial']=initial_sp
    if repeat:p['abilities'][1]['timeline'][0]['repeat']={'count':2,'interval_seconds':0}
    p['entities'].append({'id':'unit/test/snmage/target','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':10000,'atk':10000,'def':9999,'mres':25,'block_count':0,'attack_speed_ratio':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1,'abnormal_immunes':list(immune)},'spatial':{},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/test/snmage/kill']}})
    p['selectors'].append({'id':'selector/test/snmage/kill','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/test/snmage/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snmage/kill','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]})
    initial=[{'definition':UID,'instanceAlias':'mage','position':{'row':0,'col':0}}]
    if second:initial.append({'definition':UID,'instanceAlias':'mage2','position':{'row':0,'col':0}})
    p['scenarioDraft']={'id':'scene/ch6/snmage/author','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':8},'resources':{'dp':{'initial':20,'capacity':99},'life':{'initial':99999,'capacity':99999}},'initialEntities':initial,'roster':['unit/test/snmage/target']}
    return p
def fixture(**kw):return Engine.create(Compiler(providers=providers()).compile(package(**kw),packages=[COLD]),seed=6268,providers=providers())
def deploy(s,at=0,col=1):s.submit({'action':'deploy','definition':'unit/test/snmage/target','alias':'target','position':{'row':0,'col':col}},at=at)
def sp(s,alias='mage'):return s.ctx.resources.current(alias,'sp')
def ready(s):return [b for b in s.ctx.get('mage',('buffs','instances'),[]) if b['definition']==READY]
def flags(s):return s.ctx.spatial.selection_state('target',DEFAULT_STATE)['abnormal_flags']
def damage(s):return [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']

def test_exact_source_and_unique_normal_native_pointer():
    assert implementation_digest()==CORE
    src=json.loads((OUT/'source.reference.json').read_bytes());d=src['variant']['native_enemy']['resolved'];a=d['attributes']
    assert (a['maxHp'],a['atk'],a['def'],a['magicResistance'],a['baseAttackTime'])==(8000,400,250,50,4)
    assert src['unique_normal_count']==1 and src['deduplicated_labels']['_combat']==src['deduplicated_labels']['_attack']
    assert d['spData']=={'spType':'INCREASE_WHEN_ATTACK','maxSp':2,'initSp':0,'increment':1}
    assert d['skills'][0]['priority']==0 and d['skills'][0]['spCost']==2

def test_no_target_no_cast_no_clock_sp_and_no_ready():
    s=fixture();s.session.advance(301)
    assert sp(s)==0 and not ready(s) and not [e for e in s.session.events if e['type']=='ability.started']

def test_actual_launch20_then_speed10_hit_sp_and_third_replacement():
    s=fixture();deploy(s);s.session.advance(21)
    assert not damage(s) and sp(s)==0
    s.session.advance(4);assert damage(s)==[(23,300)] and sp(s)==1 and not ready(s)
    s.session.advance(120);assert damage(s)==[(23,300),(143,300)] and sp(s)==2
    s.session.advance(1);assert len(ready(s))==1
    s.session.advance(96);assert sp(s)==0 and not ready(s)
    starts=[(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started']
    assert starts==[(0,NORMAL),(120,NORMAL),(240,SKILL)]
    s.session.advance(21);assert 23 not in flags(s)
    s.session.advance(1);assert damage(s)==[(23,300),(143,300),(263,300)] and 23 in flags(s) and sp(s)==0
    inst=next(b for b in s.ctx.get('target',('buffs','instances'),[]) if b['definition']=='buff/ch6/cold/e2c_cold')
    assert inst['expires_at']==563 and s.ctx.attributes.value('target','attack_speed_ratio')==pytest.approx(.7)
    assert len([e for e in s.session.events if e['type']=='projectile.launched'])==3

def test_duplicate_payload_hits_still_charge_once_per_real_attack():
    s=fixture(repeat=True);deploy(s);s.session.advance(25)
    assert damage(s)==[(23,300),(23,300)] and sp(s)==1
    assert len([e for e in s.session.events if e['type']=='attack.accepted'])==1

def test_actual_initial_full_sp_ready_and_cost_then_no_skill_recovery():
    s=fixture(initial_sp=2);assert len(ready(s))==1
    deploy(s);s.session.advance(2)
    assert sp(s)==0 and not ready(s)
    assert [e['payload']['ability'] for e in s.session.events if e['type']=='ability.started']==[SKILL]
    s.session.advance(23);assert damage(s)==[(23,300)] and sp(s)==0 and 23 in flags(s)

def test_cold_payload_never_launch_time_and_cancelled_target_grants_no_sp():
    s=fixture(initial_sp=2);deploy(s);s.submit({'action':'withdraw','source':'target'},at=22)
    s.session.advance(31)
    assert not damage(s) and sp(s)==0 and not ready(s)
    assert not [e for e in s.session.events if e['type']=='attack.accepted']
    assert [e for e in s.session.events if e['type']=='projectile.invalid' and e['payload']['reason']=='target_invalid']

def test_shared_range2point2_rejects_outside_and_never_sp_recovers():
    s=fixture();deploy(s,col=3);s.session.advance(151)
    assert not damage(s) and sp(s)==0

@pytest.mark.parametrize('immune,expected', [([],16),([16],23),([23],None)])
def test_two_exact_mages_public_hits_cross_source_frozen_or_immune(immune,expected):
    s=fixture(initial_sp=2,second=True,immune=immune);deploy(s);s.session.advance(25)
    assert damage(s)==[(23,300),(23,300)]
    assert sp(s)==sp(s,'mage2')==0
    assert (expected in flags(s)) if expected is not None else not flags(s)
    b=[b for b in s.ctx.get('target',('buffs','instances'),[]) if b['definition'].startswith('buff/ch6/cold/e2c')]
    assert len(b)==(1 if expected else 0)
    if b:assert b[0]['expires_at']==323

def test_public_lethal_source_after_launch_retains_projectile_but_no_sp():
    s=fixture();deploy(s);s.submit({'action':'skill','source':'target','ability':'ability/test/snmage/kill'},at=22)
    s.session.advance(25)
    assert not s.ctx.alive('mage') and sp(s)==0
    assert damage(s)==[(22,8000),(23,300)]
    assert not [e for e in s.session.events if e['type']=='attack.accepted']

def test_public_manual_auto_only_skill_rejects_without_cost_or_cast():
    s=fixture(initial_sp=2);s.submit({'action':'skill','source':'mage','ability':SKILL},at=0);s.session.advance(1)
    assert sp(s)==2 and len(ready(s))==1 and not [e for e in s.session.events if e['type']=='ability.started']
    assert [e for e in s.session.events if e['type']=='command.rejected']

def test_actual_ready_pending_projectile_and_cold_disk_cp_head_replay(tmp_path):
    s=fixture();deploy(s);s.session.advance(146);assert len(ready(s))==1
    p=tmp_path/'actual.snmage.json';pin=write_ordered(p,s.checkpoint());restored=Engine.restore(s.program,load_bound(p,pin),providers=providers())
    s.session.advance(419);restored.session.advance(419)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
    assert not flags(s)


def controlled_package(*,cold=False):
    p=package(initial_sp=2)
    controller={'id':'unit/test/snmage/controller','kind':'entity','tags':['test_controller'],'components':{'attributes':{'base':{'max_hp':10}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    if cold:
        p['entities'][0]['tags'].append('cold_receiver')
        controller['components']['abilities']=['ability/ch6/cold/apply5']
    else:
        p['buffs'].append({'id':'buff/test/snmage/silence','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_flags':[12]}})
        p['abilities'].append({'id':'ability/test/snmage/silence','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snmage/kill','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/test/snmage/silence'}}]})
        controller['components']['abilities']=['ability/test/snmage/silence']
    p['entities'].append(controller);p['scenarioDraft']['initialEntities'].append({'definition':controller['id'],'instanceAlias':'controller','position':{'row':1,'col':7}})
    return p


def test_public_silence_blocks_only_skill_preserves_full_ready_then_falls_back_normal():
    s=Engine.create(Compiler(providers=providers()).compile(controlled_package(),packages=[COLD]),seed=6268,providers=providers())
    s.submit({'action':'skill','source':'controller','ability':'ability/test/snmage/silence'},at=0);deploy(s,at=1)
    s.session.advance(25)
    starts=[(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==s.session.world.resolve('mage')]
    assert starts==[(1,NORMAL)] and sp(s)==2 and len(ready(s))==1
    s.session.advance(97)
    assert sp(s)==0 and not ready(s)
    assert [(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==s.session.world.resolve('mage')]==[(1,NORMAL),(121,SKILL)]


def test_public_source_frozen_blocks_full_sp_cast_without_sp_or_ready_loss_until_expiry():
    s=Engine.create(Compiler(providers=providers()).compile(controlled_package(cold=True),packages=[COLD]),seed=6268,providers=providers())
    for tick in (0,1):s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=tick)
    deploy(s,at=2);s.session.advance(150)
    assert sp(s)==2 and len(ready(s))==1 and not damage(s)
    assert 16 in s.ctx.spatial.selection_state('mage',DEFAULT_STATE)['abnormal_flags']
    s.session.advance(3)
    assert sp(s)==0 and not ready(s)
    assert [e['payload']['ability'] for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==s.session.world.resolve('mage')]==[SKILL]
