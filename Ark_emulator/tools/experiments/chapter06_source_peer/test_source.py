import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.campaign_content_composition import compose_modules
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[];CAPTURES=[]
def module(name):return json.loads((ROOT/'packages/campaign/chapter06_units'/name/'model.json').read_bytes())
def fixture(name,uid=None,two=False):
 source=module(name);cold=json.loads((ROOT/'packages/campaign/chapter06_cold/model.json').read_bytes());defs,_=compose_modules([('source',source),('cold',cold)]);uid=uid or source['entities'][0]['id']
 controls=[('freeze_target',{'op':'apply_buff','target':3,'buff':'buff/ch6/cold/e2c_freeze'}),('cold_source',{'op':'buff_application','target':2,'application_rule':'rule/ch6/cold/application','allowed':['buff/ch6/cold/e2c_cold','buff/ch6/cold/e2c_freeze'],'parameters':{'duration_seconds':10}}),('silence_source',{'op':'apply_buff','target':2,'buff':'buff/peer/silence'}),('kill_source',{'op':'modify_resource','target':2,'resource':'hp','value':0}),('withdraw_target',{'op':'retire','target':3,'parameters':{'reason':'withdrawn'}})]
 for key,e in controls:defs['ability/peer/'+key]={'id':'ability/peer/'+key,'kind':'ability','activation':{'mode':'manual','on_start':[e]},'timeline':[]}
 defs['buff/peer/silence']={'id':'buff/peer/silence','kind':'buff','duration_seconds':10,'selection_flags':{'abnormal_flags':[12]}}
 for key,hp,block in [('tank',20000,3),('controller',1000,0)]:
  defs['unit/peer/'+key]={'id':'unit/peer/'+key,'kind':'entity','tags':['player','ground'],'components':{'attributes':{'base':{'max_hp':hp,'atk':0,'def':31,'mres':17,'block_count':block,'attack_speed_ratio':1,'move_speed':0}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{'radius':0},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':['ability/peer/'+k for k,_ in controls] if key=='controller' else [],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 p={'schemaVersion':2,'manifest':{'id':'package/independent/ch6/source','requires':['preset/ark_standard']},'definitions':list(defs.values()),'scenarioDraft':{'id':'scene/independent/ch6/'+name,'ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':5},'parameters':{'deploy_capacity':3},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999},'dp':{'initial':50,'capacity':99}},'roster':['unit/peer/tank','unit/peer/controller'],'initialEntities':[{'definition':uid,'instanceAlias':'adversary','position':{'row':1,'col':1},'route':{'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':4},'checkpoints':[]}}]}}
 commands=[{'action':'deploy','definition':'unit/peer/tank','alias':'tank','position':{'row':1,'col':1},'facing':'left'},{'action':'deploy','definition':'unit/peer/controller','alias':'controller','position':{'row':3,'col':4},'facing':'left'}]
 if two:commands.append({'action':'deploy','definition':'unit/peer/tank','alias':'tank2','position':{'row':1,'col':2},'facing':'left'})
 return p,commands
def make(p,commands):
 INPUTS.append({'package':deepcopy(p),'commands':deepcopy(commands)});reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),seed=64041,providers=reg)
 for c in commands:s.submit(c,at=0)
 return s
def skill(s,key,at):s.submit({'action':'skill','source':'controller','ability':'ability/peer/'+key},at=at)
def event(s,name):return [thaw(e) for e in s.session.events if e['type']==name]
def capture(s,name):CAPTURES.append({'case':name,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def exact(s,tmp,n):
 path=tmp/'source_before.json';h=write_ordered(path,s.checkpoint());reg=providers();r=Engine.restore(s.program,load_bound(path,h),providers=reg);s.advance(n);r.advance(n);head=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
@pytest.mark.parametrize('name,index,frame,atk,scale',[('melee_v2',0,14,600,1),('melee_v2',1,12,360,1.5),('frozen_melee',0,16,430,1.5),('frozen_melee',1,29,830,2.5)])
def test_source_melee_target_frozen_after_cast_is_read_on_real_damage(name,index,frame,atk,scale,tmp_path):
 uid=module(name)['entities'][index]['id'];p,c=fixture(name,uid);s=make(p,c);skill(s,'freeze_target',5);s.advance(4);exact(s,tmp_path,frame+5);capture(s,uid+'_frozen_during_windup')
 hits=event(s,'damage.accepted');starts=[e for e in event(s,'ability.started') if e['payload']['source']==2]
 assert len(hits)==1 and hits[0]['time']-starts[0]['time']==frame and hits[0]['payload']['amount']==atk*scale-31
@pytest.mark.parametrize('name,index,frame,atk',[('melee_v2',0,14,600),('melee_v2',1,12,360),('frozen_melee',0,16,430),('frozen_melee',1,29,830)])
def test_source_cold_pointseven_scales_actual_windup_by_ceil(name,index,frame,atk):
 uid=module(name)['entities'][index]['id'];p,c=fixture(name,uid);s=make(p,c);skill(s,'cold_source',0);s.advance(50);capture(s,uid+'_cold_source')
 hits=event(s,'damage.accepted');starts=[e for e in event(s,'ability.started') if e['payload']['source']==2];assert hits[0]['time']-starts[0]['time']==__import__('math').ceil(frame/.7) and hits[0]['payload']['amount']==atk-31
def test_snmage_two_real_normal_hits_charge_ready_then_skill_cost_two_no_extra_recovery(tmp_path):
 p,c=fixture('snmage_v2');s=make(p,c);s.advance(130);exact(s,tmp_path,170);capture(s,'snmage_real_charge')
 starts=[e for e in event(s,'ability.started') if e['payload']['source']==2];hits=event(s,'damage.accepted');assert [e['payload']['amount'] for e in hits]==[332,332,332]
 assert [e['payload']['ability'].split('/')[-1] for e in starts]==['normal','normal','coldattack']
 changes=[e for e in event(s,'resource.changed') if e['payload']['target']==2 and e['payload']['resource']=='sp'];assert [e['payload']['delta'] for e in changes]==[1,1,-2] and s.ctx.resources.current('adversary','sp')==0
 assert [e['payload']['buff'] for e in event(s,'buff.applied') if e['payload']['target']==3]==['buff/ch6/cold/e2c_cold']
def test_snslime_actual_death_aoe_def31_one_packet_each_and_cold_timers(tmp_path):
 p,c=fixture('snslime',two=True);s=make(p,c);skill(s,'kill_source',2);s.advance(10);exact(s,tmp_path,28);capture(s,'snslime_true_source_death')
 hits=event(s,'damage.accepted');assert [(e['payload']['target'],e['payload']['amount']) for e in hits]==[(3,569),(5,569)]
 assert all(e['time']==32 and e['payload']['damage_flags']=={'source_attack_type':'SPLASH','ignore_for_sp':False} for e in hits)
 assert not s.ctx.active('adversary') and s.ctx.resources.current('adversary','hp')==0
 for target in ['tank','tank2']:assert s.ctx.get(target,('buffs','instances'))[0]['expires_at']==332
def test_snslime_source_silence_true_bson_gate_prevents_death_projectile():
 p,c=fixture('snslime',two=True);s=make(p,c);skill(s,'silence_source',1);skill(s,'kill_source',2);s.advance(38);capture(s,'snslime_silence')
 assert not event(s,'projectile.launched') and not event(s,'damage.accepted')
