"""Independent numerical goldens from frozen source, real public commands and CP/head."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_special.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2]
def package(name,blocked=False):
 p=json.loads((ROOT/'packages/campaign/chapter08_consumers/special'/f'{name}.module.v1.json').read_bytes());uid=p['entities'][0]['id']
 p['manifest']['metadata']['author_fixture']='Isolated public controller/target units, not native operator skill or complete stage; enemy source stats and timings unchanged.'
 p['scenarioDraft']={'id':'scene/ch8/special/'+name,'ruleset':'ruleset/ark_standard','map':{'rows':6,'cols':6},'objectives':{},'resources':{'dp':{'initial':20,'capacity':99}},'initialEntities':[{'definition':uid,'instanceAlias':'enemy','position':{'row':2,'col':2},'route':{'motionMode':'WALK','startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':5},'checkpoints':[]}}]}
 for alias,row,col,defense,motion,camo in [('near',2,2 if blocked else 3,100,1,False),('other',2,4,120,1,False),('air',1,3,140,2,False),('camo',2,3.5,180,1,True),('outer',2,4.21,200,1,False)]:
  id='unit/test/c8/special/'+alias;components={'attributes':{'base':{'max_hp':100000,'atk':1,'def':defense,'mres':25,'block_count':3 if alias=='near' and blocked else 0,'taunt_level':0}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},'selection_state':{'side':0,'motion':motion,'category':1,'unit_type':1,'camouflage':camo},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}
  p['entities'].append({'id':id,'kind':'entity','tags':['player',alias],'components':components});p['scenarioDraft']['initialEntities'].append({'definition':id,'instanceAlias':alias,'position':{'row':row,'col':col}})
 p['selectors'].append({'id':'selector/test/c8/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
 return p
def ability(p,name,effect,selector='selector/test/c8/enemy'):
 id='ability/test/c8/'+name;p['abilities'].append({'id':id,'kind':'ability','activation':{'mode':'manual'},'selector':selector,'timeline':[{'at':0,'effect':effect}]});p['entities'][1]['components']['abilities'].append(id);return id
def fixed_damage(p,amount,name='damage'):
 r='rule/test/c8/'+name;p['rules'].append({'id':r,'kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':"+str(amount)+",'allocations':[],'events':[]}"}],'output':'nodes.result'}});return ability(p,name,{'op':'damage','damage_type':'true','rules':{'damage.pipeline':r}})
def make(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=812)
def packets(s,alias=None):
 return [e for e in s.session.events if e['type']=='damage.accepted' and (alias is None or e['payload'].get('target')==s.session.world.resolve(alias))]
def test_emppnt_one_same_pointer_payload_one_delayed_circle_all_eligible_members():
 s=make(package('emppnt'));s.session.advance(105);hits=packets(s);assert [(e['time'],e['payload']['amount']) for e in hits]==[(100,900),(100,880),(100,860),(100,820)]
 assert {e['payload']['target'] for e in hits}=={s.session.world.resolve(n) for n in ['near','other','air','camo']}
 assert s.ctx.resources.current('outer','hp')==100000
 assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
 assert len([e for e in s.session.events if e['type']=='area.resolved'])==1
 assert {b['definition'] for b in s.ctx.get('enemy',('buffs','instances'),[])}=={'buff/ch8/emppnt/emppnt_scaning_buff','buff/ch8/emppnt/emppnt_scaning_buff_02'}
def test_emppnt_static_target_point_does_not_follow_target_after_launch():
 p=package('emppnt');move=ability(p,'move',{'op':'move','target':'source','row':2,'col':5});s=make(p);s.submit({'action':'skill','source':'near','ability':move},at=11);s.session.advance(105)
 assert not packets(s,'near') and len(packets(s))==3 and all(e['time']==100 for e in packets(s))
def test_emppnt_dead_source_existing_projectile_still_actual_area_damage():
 p=package('emppnt');retire=ability(p,'retire',{'op':'retire','target':1});s=make(p);s.submit({'action':'skill','source':'near','ability':retire},at=11);s.session.advance(105)
 assert not s.ctx.alive('enemy') and len(packets(s))==4 and all(e['time']==100 for e in packets(s))
def test_emppnt_live_marker_preference_and_onattack_refresh_no_finite_taunt_constant():
 p=package('emppnt');p['entities'][2]['components']['attributes']['base']['taunt_level']=1e12
 mark=ability(p,'mark_self',{'op':'apply_buff','target':'source','buff':'buff/ch8/source/mark_neutral[effect]'});s=make(p);s.submit({'action':'skill','source':'near','ability':mark},at=5);s.session.advance(11)
 launch=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launch)==1 and launch[0]['payload']['target']==s.session.world.resolve('near')
def test_empace_real_blocked_melee_numeric_frames_and_attack_exclusion():
 s=make(package('empace',True));s.session.advance(20);hits=packets(s,'near');assert [(e['time'],e['payload']['amount']) for e in hits]==[(15,800)]
 assert not [e for e in s.session.events if e['type']=='projectile.launched']
def test_empace_unblocked_halfscale_homing_ground_only_actual_frame():
 s=make(package('empace'));s.session.advance(40);hits=packets(s,'near');assert len(hits)==1 and hits[0]['time']==34 and hits[0]['payload']['amount']==350
 assert not packets(s,'air') and not packets(s,'camo')
def test_empace_inclusive_half_damage_at_hit_then_heal_above_and_retrigger():
 p=package('empace',True);d=fixed_damage(p,6000);heal=ability(p,'heal',{'op':'modify_resource','resource':'hp','delta':1});d1=fixed_damage(p,1,'one');s=make(p)
 s.submit({'action':'skill','source':'near','ability':d},at=5);s.submit({'action':'skill','source':'near','ability':heal},at=20);s.submit({'action':'skill','source':'near','ability':d1},at=151);s.session.advance(290)
 hits=packets(s,'near');assert [(e['time'],e['payload']['amount']) for e in hits]==[(15,1700),(150,800),(285,1700)]
def test_empace_half_passive_not_silenced_and_dynamic_effective_maxhp():
 p=package('empace',True);b='buff/test/c8/maxhp';p['buffs'].append({'id':b,'kind':'buff','modifiers':[{'attribute':'max_hp','layer':'direct_ratio','value':1}]});p['entities'][0]['components']['buffs']['initial'].append(b)
 p['entities'][0]['components']['resources']['hp']['initial']=24000;d=fixed_damage(p,12000);sil='buff/test/c8/silence';p['buffs'].append({'id':sil,'kind':'buff','selection_flags':{'abnormal_flags':[12]}});a=ability(p,'silence',{'op':'apply_buff','buff':sil});s=make(p);s.submit({'action':'skill','source':'near','ability':d},at=5);s.submit({'action':'skill','source':'near','ability':a},at=6);s.session.advance(20)
 assert packets(s,'near')[0]['payload']['amount']==1700
@pytest.mark.parametrize('name,tick,end',[('emppnt',11,105),('empace',32,40),('empace',6,20)])
def test_disk_inflight_or_half_threshold_cp_and_all_public_head(name,tick,end,tmp_path):
 p=package(name,name=='empace' and tick==6)
 if tick==6:
  d=fixed_damage(p,6000);s=make(p);s.submit({'action':'skill','source':'near','ability':d},at=5)
 else:s=make(p)
 s.session.advance(tick);cp=tmp_path/'proof.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h),providers=providers());s.session.advance(end-tick);r.session.advance(end-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
