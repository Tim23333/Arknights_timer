from pathlib import Path
from copy import deepcopy
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.dragon_fire_policies_v3 import providers as fire
from tools.chapter08_buff_lifetime.policies_v1 import providers as clock
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v12.joint.json';INPUTS=[];CAPTURES=[]
REG={**fire(),**clock()};PARENT='buff/ch8/source/dragon_fire';CHILD=PARENT+'[damage]'
def nested_rate(inputs,params,context):
 assert context['seconds']==inputs['clock']['time']*inputs['clock']['quantum']
 return context.calculate('buff.lifetime_rate',inputs,rule_id='rule/ch8/dragon_fire/dynamic_rate').value
def package():
 m=json.loads(MODULE.read_bytes());return {'schemaVersion':2,'manifest':{'id':'package/peer/dragonclock','requires':['preset/ark_standard']},'buffs':[{'id':'buff/peer/resistance','kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'final_ratio','value':-.5}]}],'entities':[{'id':'unit/peer/fireowner','kind':'entity','components':{'attributes':{'base':{'max_hp':3131,'atk':493,'def':81,'mres':17}},'resources':{'hp':{'initial':3131,'capacity':3131,'role':'health'}},'spatial':{},'abilities':['ability/peer/fire','ability/peer/retire'],'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/firetarget','kind':'entity','components':{'attributes':{'base':{'max_hp':70000,'atk':217,'def':31,'mres':17,'one_minus_status_resistance':1}},'resources':{'hp':{'initial':70000,'capacity':70000,'role':'health'}},'spatial':{},'abilities':['ability/peer/resistance'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'abilities':[{'id':'ability/peer/fire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'buff_application','target':3,'application_rule':'rule/ch8/dragon_fire/application','allowed':[PARENT,CHILD]}]},'timeline':[]},{'id':'ability/peer/resistance','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'self','buff':'buff/peer/resistance'}]},'timeline':[]},{'id':'ability/peer/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'self','parameters':{'reason':'peer_source_exit'}}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/dragonclock','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/fireowner','instanceAlias':'fireowner','position':{'row':0,'col':0}},{'definition':'unit/peer/firetarget','instanceAlias':'firetarget','position':{'row':0,'col':1}}]}}
def make():
 p=package();INPUTS.append(deepcopy(p));program=Compiler(providers=REG).compile(p,packages=[str(MODULE)]);return Engine.create(program,providers=REG,seed=8819311)
def proof(s,tmp_path,split,end):
 s.advance(split);pin=write_ordered(tmp_path/'dragon.cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'dragon.cp.json',pin),providers=REG);s.advance(end-split);r.advance(end-split);h=replay(s.program,s.export_replay(),providers=REG);assert s.checkpoint()==r.checkpoint()==h.checkpoint();CAPTURES.append({'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def test_source_nominal30_5_at11_resistance311_expiry619_child_cadence_and_damage_not_actor_atk(tmp_path):
 s=make();s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'firetarget','ability':'ability/peer/resistance'},at=311);proof(s,tmp_path,310,630)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[11+30*n for n in range(1,21)] and [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,21)]
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==PARENT]==[619]
 rows=s.ctx.get('firetarget',('buffs','instances'));assert not any(b['definition']==PARENT for b in rows) and len([b for b in rows if b['definition']==CHILD])==1 and s.ctx.resources.current('firetarget','hp')==70000-sum(50+6*n for n in range(1,21))
def test_actual_source_retirement_keeps_existing_dynamic_parent_and_child_timers(tmp_path):
 s=make();s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/retire'},at=21);proof(s,tmp_path,20,80)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[41,71] and [e['payload']['amount'] for e in hits]==[56,62] and not s.ctx.active('fireowner')
 assert {b['definition'] for b in s.ctx.get('firetarget',('buffs','instances'))}=={PARENT,CHILD}
def test_source_live_parent_refresh_uses_full_new_nominal_time_without_resetting_child_ramp(tmp_path):
 s=make();s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'firetarget','ability':'ability/peer/resistance'},at=311);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=311);proof(s,tmp_path,310,780)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[11+30*n for n in range(1,26)] and [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,26)]
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==PARENT]==[769]
 assert [e['time'] for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==CHILD]==[11]
def test_source_timer_absence_reignite_reuses_child_uid_but_resets_generation_phase_and_ramp(tmp_path):
 s=make();s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'firetarget','ability':'ability/peer/resistance'},at=311);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=650);proof(s,tmp_path,649,720)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[11+30*n for n in range(1,21)]+[680,710] and [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,21)]+[56,62]
 applications=[e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==CHILD];assert [e['time'] for e in applications]==[11,650] and applications[0]['payload']['instance']==applications[1]['payload']['instance']
 child=next(b for b in s.ctx.get('firetarget',('buffs','instances')) if b['definition']==CHILD);assert child['started_at']==650 and child['generation']==2
def test_declared_attr26_zero_minimum_clamp_expires_next_tick_before_child_first_packet(tmp_path):
 p=package();p['entities'][1]['components']['attributes']['base']['one_minus_status_resistance']=0;INPUTS.append(deepcopy(p));program=Compiler(providers=REG).compile(p,packages=[str(MODULE)]);s=Engine.create(program,providers=REG,seed=8819311);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);proof(s,tmp_path,12,50)
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==PARENT]==[12] and not any(e['type']=='damage.accepted' for e in s.session.events)
def test_declared_attr26_high_maximum_clamp_keeps_nominal_clock_slow_and_child_world_clock(tmp_path):
 p=package();p['entities'][1]['components']['attributes']['base']['one_minus_status_resistance']=2000;INPUTS.append(deepcopy(p));program=Compiler(providers=REG).compile(p,packages=[str(MODULE)]);s=Engine.create(program,providers=REG,seed=8819311);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);proof(s,tmp_path,40,80)
 parent=next(b for b in s.ctx.get('firetarget',('buffs','instances')) if b['definition']==PARENT);assert parent['lifetime_clock']['rate']==.001 and parent['lifetime_clock']['remaining_seconds']>30.49
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[41,71] and [e['payload']['amount'] for e in hits]==[56,62]
def test_source_clock_explicit_wrapper_nested_calculation_has_exact_time_seconds_and_same_consumption(tmp_path):
 p=package();m=json.loads(MODULE.read_bytes());m['rules'].append({'id':'rule/peer/nested_lifetime','kind':'rule','contract':'buff.lifetime_rate','dependencies':['rule/ch8/dragon_fire/dynamic_rate'],'implementation':{'type':'provider','provider':'peer.nested_rate'}});next(b for b in m['buffs'] if b['id']==PARENT)['lifetime']['rule']='rule/peer/nested_lifetime';INPUTS.append({'fixture':deepcopy(p),'controlled_rule_overlay':deepcopy(m)})
 reg={**REG,'peer.nested_rate':{'callable':nested_rate,'version':'1'}};program=Compiler(providers=reg).compile(p,packages=[m]);s=Engine.create(program,providers=reg,seed=8819311);s.submit({'action':'skill','source':'fireowner','ability':'ability/peer/fire'},at=11);s.submit({'action':'skill','source':'firetarget','ability':'ability/peer/resistance'},at=311);s.advance(310);pin=write_ordered(tmp_path/'nested310.json',s.checkpoint());r=Engine.restore(program,load_bound(tmp_path/'nested310.json',pin),providers=reg);s.advance(320);r.advance(320);h=replay(program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint();CAPTURES.append({'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==PARENT]==[619] and len([e for e in s.session.events if e['type']=='damage.accepted'])==20

