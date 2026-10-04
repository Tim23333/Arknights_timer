import hashlib,json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.build_chapter04_demon_dynamic import build,OUT
UID='unit/ch4/enemy_1010_demon/b6763feff65e5ee5';AID='ability/'+UID;CAPTURES=[]
def fixture(phase):
 path=OUT/(phase+'.model.json');raw=path.read_bytes();p=json.loads(raw);assert p==build(phase)
 guard={'id':'unit/dynamic_guard','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':25000,'def':157,'block_count':1}},'resources':{'hp':{'initial':25000,'capacity':25000,'role':'health'}},'deployable':{'base_cost':5,'capacity':1,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':2}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/probe_stop','ability/probe_branch','ability/probe_trigger']}};p['entities'].append(guard)
 p['selectors'].append({'id':'selector/probe_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 p['buffs']=[{'id':'buff/probe_stop','kind':'buff','duration_seconds':.5,'control':{'move':False,'attack':False,'abilities':False,'interrupt':True}}]
 p['abilities'].extend([{'id':'ability/probe_stop','kind':'ability','selector':'selector/probe_enemy','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/probe_stop'}]},'timeline':[]},{'id':'ability/probe_branch','kind':'ability','selector':'selector/probe_enemy','activation':{'mode':'manual','on_start':[{'op':'modify_resource','resource':'animation_branch','value':1}]},'timeline':[]},{'id':'ability/probe_trigger','kind':'ability','selector':'selector/probe_enemy','activation':{'mode':'manual','costs':[{'owner':'battle','resource':'dp','amount':1}],'on_start':[{'op':'trigger_ability','ability':AID}]},'timeline':[]}])
 p['scenarioDraft']={'id':'scene/demon_dynamic','ruleset':'ruleset/ark_standard','roster':['unit/dynamic_guard'],'resources':{'dp':{'initial':30,'capacity':30},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'map':{'rows':3,'cols':6},'waves':[{'at':0,'definition':UID,'instanceAlias':'demon','position':{'row':1,'col':0},'route':{'motionMode':0,'startPosition':{'row':1,'col':0},'endPosition':{'row':1,'col':5},'checkpoints':[]}}]}
 return p,hashlib.sha256(raw).hexdigest()
def create(phase):
 p,h=fixture(phase);raw=(json.dumps(p,indent=2)+'\n').encode();s=Engine.create(Compiler().compile(json.loads(raw)),seed=405010);s.submit({'action':'deploy','entity':'unit/dynamic_guard','alias':'guard','position':{'row':1,'col':0}},at=4);return s,{'package_sha256':h,'fixture_sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':405010}
def finish(s,inputs,tmp,expected):
 s.advance(72);h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(70);r.advance(70);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();CAPTURES.append({'input':inputs,'expected':expected,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'commands':s.export_replay(),'checkpoint_sha256':h,'checkpoint_equal':True,'commands_replay_equal':True})
def events(s,kind):return [e for e in s.session.events if e['type']==kind and e['payload'].get('source')==s.session.world.resolve('demon')]
@pytest.mark.parametrize('phase',['start','first_hit','finish'])
def test_first27_then15_single_clock_and_captured_branch(phase,tmp_path):
 s,inputs=create(phase);s.advance(6);cast=s.ctx.get('demon',('runtime','casts'))['cast/2/1'];assert cast['source_snapshot']['components']['resources']['captured_animation_branch']['current']==0
 finish(s,inputs,tmp_path,{'cast_starts':[5,65,125],'hit_times':[32,80,140],'finish_times':[50,98],'damage':443})
 assert [e['time'] for e in events(s,'ability.started')][:3]==[5,65,125];assert [e['time'] for e in events(s,'damage.accepted')][:3]==[32,80,140];assert [e['time'] for e in events(s,'ability.finished')][:2]==[50,98];assert all(e['payload']['amount']==443 for e in events(s,'damage.accepted'))
 assert len(s.ctx.get('demon',('abilities',)))==1 and s.ctx.resources.current('demon','captured_animation_branch')==1


def test_public_midcast_branch_change_does_not_retime_queued_tasks(tmp_path):
 s,inputs=create('finish');s.submit({'action':'skill','source':'guard','ability':'ability/probe_branch'},at=10);s.advance(11)
 cast=s.ctx.get('demon',('runtime','casts'))['cast/2/1'];assert cast['source_snapshot']['components']['resources']['captured_animation_branch']['current']==0 and cast['finish_at']==50
 finish(s,inputs,tmp_path,{'first_hit':32,'first_finish':50,'second_hit':80,'midcast_change':10});assert [e['time'] for e in events(s,'damage.accepted')][:2]==[32,80]

@pytest.mark.parametrize('phase,next_frame',[('start',15),('first_hit',27),('finish',27)])
def test_interrupt_before_first_packet_consumption_policy_explicit(phase,next_frame,tmp_path):
 s,inputs=create(phase);s.submit({'action':'skill','source':'guard','ability':'ability/probe_stop'},at=8);finish(s,inputs,tmp_path,{'interrupted_cast':5,'interruption':8,'next_cast':65,'next_frame':next_frame})
 assert events(s,'ability.interrupted')[0]['time']==8;assert [e['time'] for e in events(s,'ability.started')][:2]==[5,65];assert events(s,'damage.accepted')[0]['time']==65+next_frame

@pytest.mark.parametrize('phase,next_frame',[('start',15),('first_hit',15),('finish',27)])
def test_interrupt_after_first_packet_consumption_policy_explicit(phase,next_frame,tmp_path):
 s,inputs=create(phase);s.submit({'action':'skill','source':'guard','ability':'ability/probe_stop'},at=40);finish(s,inputs,tmp_path,{'first_hit':32,'interruption':40,'next_cast':65,'next_frame':next_frame});assert [e['time'] for e in events(s,'damage.accepted')][:2]==[32,65+next_frame]

@pytest.mark.parametrize('phase,next_frame',[('start',15),('first_hit',27),('finish',15)])
def test_public_blocker_withdraw_and_reacquire_missing_hit_policy(phase,next_frame,tmp_path):
 s,inputs=create(phase);s.submit({'action':'withdraw','entity':'guard'},at=8);s.submit({'action':'deploy','entity':'unit/dynamic_guard','alias':'guard2','position':{'row':1,'col':1}},at=70);finish(s,inputs,tmp_path,{'first_target_withdraw':8,'new_blocker_deploy':70,'new_cast':71,'new_frame':next_frame})
 starts=events(s,'ability.started');assert starts[0]['time']==5 and starts[1]['time']==71;hits=events(s,'damage.accepted');assert hits[0]['time']==71+next_frame and hits[0]['payload']['target']==s.session.world.resolve('guard2');assert s.ctx.spatial.blocked_by('demon')==s.session.world.resolve('guard2')


def test_bad_branch_rule_public_trigger_rolls_payment_tasks_rng_and_cast_back():
 p,h=fixture('finish');p['rules'][-2]['implementation']['expression']='1 / 0';wave=p['scenarioDraft']['waves'][0];p['scenarioDraft']['waves']=[];p['scenarioDraft']['initialEntities']=[{'definition':UID,'instanceAlias':'demon','position':{'row':1,'col':0},'route':wave['route']},{'definition':'unit/dynamic_guard','instanceAlias':'guard','position':{'row':1,'col':0}}]
 raw=(json.dumps(p,indent=2)+'\n').encode();s=Engine.create(Compiler().compile(json.loads(raw)),seed=405010);before=s.checkpoint()
 with pytest.raises(Exception):
  with s.session.atomic():s._execute_command({'action':'skill','source':'guard','ability':'ability/probe_trigger'})
 assert s.checkpoint()==before
 CAPTURES.append({'input':{'fixture_sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':405010},'scope':'public API instrumentation atomic failure, not command replay','expected':'complete payment/cast/tasks/RNG/log rollback','checkpoint':s.checkpoint()})
