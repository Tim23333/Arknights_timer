import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];MODULE=ROOT/'packages/campaign/chapter05_boss/faust/combat.v4.reference.json';SOURCE=ROOT/'packages/campaign/chapter05_sources/native.reference.json';INPUTS=[];CAPTURES=[]
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()=='357abc09e1aa12410d36353769cf8f0c7416fcd12c1556098d01e6c0c7855ee4'
def fixture(isolate_movement=False,no_targets=False):
 p=json.loads(MODULE.read_bytes());unit=p['entities'][0]
 if isolate_movement:unit['components']['abilities']=[];unit['components'].pop('ability_arbitration');unit['components'].pop('behavior')
 hero={'id':'unit/peer/hero','kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':20000,'atk':100,'def':37,'mres':0,'block_count':1}},'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'abilities':['ability/peer/boost','ability/peer/armor','ability/peer/immune3','ability/peer/strike','ability/peer/mark'],'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 p['entities'].append(hero);p['buffs'].extend([{'id':'buff/peer/boost','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':200}]},{'id':'buff/peer/armor','kind':'buff','modifiers':[{'attribute':'def','layer':'flat','value':100}]},{'id':'buff/peer/immune3','kind':'buff','duration_seconds':.1,'active_rule':'rule/ch5/faust/active','selection_flags':{'abnormal_immunes':[3]}}])
 p['abilities'].extend([{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':[effect]},'timeline':[]} for name,effect in [('boost',{'op':'apply_buff','target':2,'buff':'buff/peer/boost'}),('armor',{'op':'apply_buff','target':'source','buff':'buff/peer/armor'}),('immune3',{'op':'apply_buff','target':2,'buff':'buff/peer/immune3'}),('strike',{'op':'damage','target':2,'damage_type':'true','scale':1}),('mark',{'op':'emit','target':'battle','event':'peer.due_command'})]])
 source={'definition':unit['id'],'instanceAlias':'boss','position':{'row':1,'col':1}};target={'definition':hero['id'],'instanceAlias':'hero','position':{'row':1,'col':2}}
 if isolate_movement:source['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':8},'checkpoints':[]};target['position']={'row':1,'col':1}
 if no_targets:target['position']={'row':8,'col':32}
 p['scenarioDraft']={'id':'scene/peer/faust','ruleset':'ruleset/ark_standard','rules':deepcopy(p['manifest']['metadata']['stage_rules']),'map':{'rows':10,'cols':35},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':25,'capacity':99}},'initialEntities':[source,target]}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=51510)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
def exact(s,tmp,n):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(n);r.advance(n);assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_source_level_stats_normal_critical_frames_and_single_slot_are_exact():
 p=json.loads(MODULE.read_bytes());s=json.loads(SOURCE.read_bytes());v=s['variants']['enemy_1508_faust@0/86350d42c005ccb6'];a=v['native_enemy']['resolved']['attributes'];base=p['entities'][0]['components']['attributes']['base']
 assert [base['max_hp'],base['atk'],base['def'],base['mres']]==[a['maxHp'],a['atk'],a['def'],a['magicResistance']]==[37000,1000,350,35]
 for ability in p['abilities']:
  anim=ability['metadata']['source_animation'];assert [e['frame'] for e in anim['events']]==[40] and anim['duration']['frame']==90
def test_live_source_atk_target_def_and_ground_selector_after_launch_disk_replay(tmp_path):
 p=fixture();air=deepcopy(p['scenarioDraft']['initialEntities'][1]);air['instanceAlias']='air';air['components']={'selection_state':{'motion':2},'spatial':{'motion_mode':1},'attributes':{'base':{'taunt_level':1000000000}}};p['scenarioDraft']['initialEntities'].append(air)
 s=make(p);s.submit({'action':'skill','source':'hero','ability':'ability/peer/boost'},at=41);s.submit({'action':'skill','source':'hero','ability':'ability/peer/armor'},at=42);s.advance(41);exact(s,tmp_path,4);capture(s,'live_at_hit_ground')
 assert [(e['time'],e['payload']['amount'],e['payload']['target']) for e in ev(s,'damage.accepted')]==[(43,1063,s.session.world.resolve('hero'))]
 assert s.ctx.resources.current('air','hp')==20000
def test_shared_normal150_critical_ready510_accepted600_damage1963(tmp_path):
 s=make(fixture());s.advance(601);exact(s,tmp_path,45);capture(s,'critical')
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(43,963),(193,963),(343,963),(493,963),(643,1963)]
 assert s.ctx.resources.current('boss','hp')==37000
def test_source_critical_empty_target_does_not_spend_clock_or_fake_cast():
 s=make(fixture(no_targets=True));s.advance(615);capture(s,'empty_critical');assert not ev(s,'ability.started') and not ev(s,'projectile.launched') and not ev(s,'damage.accepted')
def test_dynamic_blockfree_immunity_expiry_same_boundary_is_coherent_and_due_command_is_pending(tmp_path):
 s=make(fixture(True));s.submit({'action':'skill','source':'hero','ability':'ability/peer/immune3'},at=0);s.submit({'action':'skill','source':'hero','ability':'ability/peer/mark'},at=3);s.advance(2)
 assert s.ctx.spatial.blocked_by('boss')==s.session.world.resolve('hero');h=write_ordered(tmp_path/'immune.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'immune.json',h));s.advance(1);r.advance(1);capture(s,'immune_expiry3')
 assert 3 in s.ctx.spatial.selection_state('boss',DEFAULT_STATE)['abnormal_flags'] and s.ctx.spatial.blocked_by('boss') is None
 assert not ev(s,'peer.due_command') and s.checkpoint()==r.checkpoint();s.advance(1);r.advance(1)
 assert ev(s,'peer.due_command') and s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_graph_wrapped_same_status_provider_preserves_required_projection_and_blockfree():
 p=fixture(True);p['rules'].append({'id':'rule/peer/wrap_block','kind':'rule','contract':'blocking.eligibility','implementation':{'type':'graph','nodes':[{'id':'same','rule':'rule/ch5/faust/block_policy','inputs':{key:'inputs.'+key for key in ['blocker','target','positions','paths','states']}}],'output':'nodes.same'}});p['scenarioDraft']['rules']['blocking.eligibility']='rule/peer/wrap_block'
 s=make(p);failure=None
 try:s.advance(2)
 except ValueError as e:failure=str(e)
 capture(s,'wrapped_status');assert failure is None and s.ctx.spatial.blocked_by('boss') is None
def test_no_opt_standard_block_rule_is_not_magically_changed_by_actor_id():
 p=fixture(True);p['scenarioDraft']['rules']['blocking.eligibility']='rule/ark_block_eligibility';s=make(p);s.advance(2);capture(s,'standard_no_opt');assert s.ctx.spatial.blocked_by('boss')==s.session.world.resolve('hero')
def test_custom_base_reject_is_consumed_when_blockfree3_is_immune():
 p=fixture(True);p['rules'].append({'id':'rule/peer/base_no','kind':'rule','contract':'blocking.eligibility','implementation':{'type':'graph','nodes':[{'id':'answer','expression':"{'accepted':False,'reason':'peer_base_no'}"}],'output':'nodes.answer'}});next(r for r in p['rules'] if r['id']=='rule/ch5/faust/block_policy')['parameters']['base_rule']='rule/peer/base_no';p['entities'][0]['components']['selection_state']['abnormal_immunes'].append(3)
 s=make(p);s.advance(2);capture(s,'replaceable_base');assert s.ctx.spatial.blocked_by('boss') is None and 3 not in s.ctx.spatial.selection_state('boss',DEFAULT_STATE)['abnormal_flags']
