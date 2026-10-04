"""Public ranging/retained crossbow/target capture and nonsilenceable passive witnesses."""
from pathlib import Path
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.chapter06_units.snbow.build_module import ROOT,OUT,COLD,CORE,UID,AID
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def package(*,two=False,motion=1,category=1,target_free=False,camouflage=False,col=1,route=False):
    p=json.loads((OUT/'model.json').read_bytes())
    for name in ('target','other') if two else ('target',):
        p['entities'].append({'id':'unit/test/snbow/'+name,'kind':'entity','tags':['player','ground','cold_receiver'],'components':{'attributes':{'base':{'max_hp':10000,'atk':5000,'def':100,'mres':0,'attack_speed_ratio':1,'block_count':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':motion,'category':category,'unit_type':1,'target_free':target_free,'camouflage':camouflage},'spatial':{},'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/test/snbow/kill']}})
    p['selectors'].append({'id':'selector/test/snbow/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    p['abilities'].append({'id':'ability/test/snbow/kill','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snbow/enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1}}]})
    p['buffs']=[{'id':'buff/test/snbow/silence','kind':'buff','duration_seconds':10,'selection_flags':{'abnormal_flags':[12]}}]
    p['abilities'].append({'id':'ability/test/snbow/silence','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/snbow/enemy','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/test/snbow/silence'}}]})
    p['entities'].append({'id':'unit/test/snbow/controller','kind':'entity','tags':['test_controller'],'components':{'attributes':{'base':{'max_hp':10}},'resources':{'hp':{'initial':10,'capacity':10,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/ch6/cold/apply5','ability/test/snbow/silence']}})
    initial={'definition':UID,'instanceAlias':'archer','position':{'row':0,'col':0}}
    if route:initial['route']={'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}
    p['scenarioDraft']={'id':'scene/ch6/snbow/author','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':8},'resources':{'dp':{'initial':30,'capacity':99},'life':{'initial':99999,'capacity':99999}},'initialEntities':[initial,{'definition':'unit/test/snbow/controller','instanceAlias':'controller','position':{'row':1,'col':7}}],'roster':['unit/test/snbow/'+n for n in ('target','other') if any(u['id']=='unit/test/snbow/'+n for u in p['entities'])]}
    return p
def fixture(**kw):return Engine.create(Compiler(providers=providers()).compile(package(**kw),packages=[COLD]),seed=6266,providers=providers())
def deploy(s,name='target',at=0,col=1,row=0):s.submit({'action':'deploy','definition':'unit/test/snbow/'+name,'alias':name,'position':{'row':row,'col':col}},at=at)
def cold(s,ticks=(13,14)):
    for at in ticks:s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=at)
def packets(s):return [(e['time'],e['payload']['target'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==s.session.world.resolve('archer')]
def hp(s,name='target'):return s.ctx.resources.current(name,'hp')

def test_exact_native_dedupe_stats_projectile_and_nonsilenceable_source():
    assert implementation_digest()==CORE
    src=json.loads((OUT/'source.reference.json').read_bytes());a=src['variant']['native_enemy']['resolved']['attributes']
    assert (a['maxHp'],a['atk'],a['def'],a['magicResistance'],a['baseAttackTime'])==(2500,290,80,0,2.4)
    assert src['dedupe']['_combat']==src['dedupe']['_attack'] and src['dedupe']['actual_payloads_per_cast']==1
    assert src['passive']['raw']['_buffs'][0]['isSilenceable']==0

def test_actual_twelve_launch_then_three_frame_flight_once_and_interval72():
    s=fixture();deploy(s);s.session.advance(12)
    assert not packets(s) and not [e for e in s.session.events if e['type']=='projectile.launched']
    s.session.advance(1);assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1 and not packets(s)
    s.session.advance(75)
    assert packets(s)==[(15,s.session.world.resolve('target'),190),(87,s.session.world.resolve('target'),190)]
    assert hp(s)==9620 and s.ctx.resources.current('system/battle','dp')==23

@pytest.mark.parametrize('motion,category,free,camo,col',[(2,1,False,False,1),(1,2,False,False,1),(1,1,True,False,1),(1,1,False,True,1),(1,1,False,False,2)])
def test_native_ground_char_target_free_camouflage_and_range_reject_before_any_cast(motion,category,free,camo,col):
    s=fixture(motion=motion,category=category,target_free=free,camouflage=camo);deploy(s,col=col);s.session.advance(80)
    assert not packets(s) and not [e for e in s.session.events if e['type']=='projectile.launched']

def test_actual_range1point9_boundary_included_and_actor_moves_stop_on_qualified_target():
    s=fixture(route=True);deploy(s,col=1);s.session.advance(80)
    assert s.ctx.get('archer',('spatial','position'))['col']<=.031
    assert len(packets(s))==1
    p=package();p['scenarioDraft']['initialEntities'][0]['position']['col']=.1
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6266,providers=providers());deploy(s,col=2);s.session.advance(19)
    assert packets(s)==[(18,s.session.world.resolve('target'),190)]

def test_target_frozen_changes_after_launch_before_impact_and_expiry_restores_plain_damage():
    s=fixture();deploy(s);cold(s);s.session.advance(232)
    target=s.session.world.resolve('target')
    assert packets(s)==[(15,target,335),(87,target,335),(159,target,335),(231,target,190)]
    assert s.ctx.attributes.value('archer','atk')==290 and hp(s)==8805

def test_public_source_silence_never_removes_native_targetfrozen_passive():
    s=fixture();deploy(s);cold(s);s.submit({'action':'skill','source':'controller','ability':'ability/test/snbow/silence'},at=1);s.session.advance(16)
    assert packets(s)==[(15,s.session.world.resolve('target'),335)] and 12 in s.ctx.spatial.selection_state('archer',DEFAULT_STATE)['abnormal_flags']

def test_cold_only_target_does_not_gain_extra_damage_or_attach_new_cold_from_arrow():
    s=fixture();deploy(s);cold(s,(13,));s.session.advance(16)
    assert packets(s)==[(15,s.session.world.resolve('target'),190)]
    assert len(s.ctx.get('target',('buffs','instances'),[]))==1

def test_source_dead_after_launch_retains_real_crossbow_without_reviving_or_new_shots():
    s=fixture();deploy(s);s.submit({'action':'skill','source':'target','ability':'ability/test/snbow/kill'},at=13);s.session.advance(90)
    assert not s.ctx.alive('archer') and hp(s,'archer')==0
    assert packets(s)==[(15,s.session.world.resolve('target'),190)] and len([e for e in s.session.events if e['type']=='projectile.launched'])==1

def test_target_withdraw_in_flight_cancels_captured_projectile_without_retargeting():
    s=fixture(two=True);deploy(s);deploy(s,'other',at=13,col=1,row=1);s.submit({'action':'withdraw','source':'target'},at=13);s.session.advance(16)
    assert not packets(s) and hp(s,'other')==10000
    assert [e for e in s.session.events if e['type']=='projectile.invalid' and e['payload']['reason']=='target_invalid']

def test_latest_actor_hatred_policy_changes_next_cast_not_current_captured_target():
    s=fixture(two=True);deploy(s);deploy(s,'other',at=5,col=1,row=1);s.session.advance(90)
    assert packets(s)==[(15,s.session.world.resolve('target'),190),(89,s.session.world.resolve('other'),190)]

def test_public_auto_only_duplicate_skill_cannot_create_second_attack_or_same_pPtr_payload():
    s=fixture();deploy(s);s.submit({'action':'skill','source':'archer','ability':AID},at=1);s.submit({'action':'skill','source':'archer','ability':AID},at=12);s.session.advance(20)
    assert len(packets(s))==1 and len([e for e in s.session.events if e['type']=='projectile.launched'])==1
    assert len([e for e in s.session.events if e['type']=='command.rejected'])==2

def test_source_singlecold_scales_twelve_to_ceil18_then_actual_flight():
    p=package();p['entities'][0]['tags'].append('cold_receiver');p['entities'][1]['tags'].remove('cold_receiver')
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6266,providers=providers());cold(s,(0,));deploy(s,at=1);s.session.advance(23)
    started=next(e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==AID);launch=next(e['time'] for e in s.session.events if e['type']=='projectile.launched')
    assert launch-started==18 and packets(s)==[(22,s.session.world.resolve('target'),190)]

@pytest.mark.parametrize('case',['live','source_dead','target_invalid'])
def test_actual_inflight_saved_checkpoint_and_full_public_head_replay(case,tmp_path):
    s=fixture();deploy(s);cold(s) if case=='live' else None
    if case=='source_dead':s.submit({'action':'skill','source':'target','ability':'ability/test/snbow/kill'},at=13)
    if case=='target_invalid':s.submit({'action':'withdraw','source':'target'},at=13)
    s.session.advance(13);p=tmp_path/'snbow.inflight.json';pin=write_ordered(p,s.checkpoint());restored=Engine.restore(s.program,load_bound(p,pin),providers=providers())
    s.session.advance(77);restored.session.advance(77)
    assert s.snapshot()==restored.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()


@pytest.mark.parametrize('kind,expected',[('physical',920),('arts',1000)])
def test_public_incoming_damage_consumes_source_def80_res0_no_phantom_healing(kind,expected):
    p=package();p['entities'][1]['components']['attributes']['base']['atk']=1000
    next(a for a in p['abilities'] if a['id']=='ability/test/snbow/kill')['timeline'][0]['effect']['damage_type']=kind
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6266,providers=providers());deploy(s);s.submit({'action':'skill','source':'target','ability':'ability/test/snbow/kill'},at=1);s.session.advance(90)
    assert hp(s,'archer')==2500-expected
    assert not [e for e in s.session.events if e['type']=='resource.changed' and e['payload'].get('target')==s.session.world.resolve('archer') and e['payload'].get('resource')=='hp' and e['payload'].get('delta',0)>0]

def test_public_target_actual_death_in_flight_cancels_no_arrow_damage():
    p=package();p['entities'][1]['components']['abilities'].append('ability/test/snbow/selfkill')
    p['abilities'].append({'id':'ability/test/snbow/selfkill','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':2}}]})
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6266,providers=providers());deploy(s);s.submit({'action':'skill','source':'target','ability':'ability/test/snbow/selfkill'},at=13);s.session.advance(16)
    assert not s.ctx.alive('target') and hp(s)==0 and not packets(s)
    assert [e for e in s.session.events if e['type']=='projectile.invalid' and e['payload']['reason']=='target_invalid']

def test_no_target_actual_route_and_base_leak_one_without_fake_damage():
    p=package(route=True);p['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'}
    s=Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6266,providers=providers());s.session.advance(150)
    assert not s.ctx.alive('archer') and hp(s,'archer')==2500
    assert s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','life')==99998
    assert not packets(s)
