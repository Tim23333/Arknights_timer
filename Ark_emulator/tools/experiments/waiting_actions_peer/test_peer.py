from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def package():
 return {'schemaVersion':2,'manifest':{'id':'package/peer/waiting','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity*inputs.parameters.ratio'}}],'buffs':[{'id':'buff/peer/timer','kind':'buff','interval_seconds':29/30,'effects':[{'op':'trigger_ability','ability':'ability/peer/wait'}]}],'abilities':[{'id':'ability/peer/wait','kind':'ability','activation':{'mode':'manual','parameters':{'auto_only':True}},'duration_seconds':.5,'timeline':[{'at':3,'effect':{'op':'emit','event':'peer.wait.impact'}}]},{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':2,'resource':'hp','value':0}]},'timeline':[]}],'entities':[{'id':'unit/peer/waiter','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':101,'atk':13}},'resources':{'hp':{'initial':101,'capacity':101,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'buffs':{'initial':['buff/peer/timer']},'abilities':['ability/peer/wait'],'rebirth':{'resource':'hp','max_count':1,'delay_seconds':100/30,'restore_ratio':1,'restore_rule':'rule/peer/restore','retain_buffs':['buff/peer/timer'],'waiting_actions':{'abilities':['ability/peer/wait'],'buffs':['buff/peer/timer']}},'spatial':{}}},{'id':'unit/peer/controller','kind':'entity','components':{'abilities':['ability/peer/kill'],'spatial':{}}}],'scenarioDraft':{'id':'scene/peer/waiting','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':2},'objectives':{},'initialEntities':[{'definition':'unit/peer/waiter','instanceAlias':'waiter','position':{'row':0,'col':0}},{'definition':'unit/peer/controller','instanceAlias':'controller','position':{'row':0,'col':1}}]}}
def make(p=None):p=p or package();INPUTS.append(deepcopy(p));s=Engine.create(Compiler().compile(p),seed=3206);s.submit({'action':'skill','source':'controller','ability':'ability/peer/kill'},at=1);return s
def capture(s,name):CAPTURES.append({'case':name,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def events(s,t):return [e for e in s.session.events if e['type']==t]
def test_actual_owned_timer29_HP0_inactive_wait_cast_with_true_disk_and_public_head(tmp_path):
 s=make();s.advance(28);assert s.ctx.resources.current('waiter','hp')==0 and not s.ctx.active('waiter');path=tmp_path/'waiting28.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.advance(74);r.advance(74);head=replay(s.program,s.export_replay());capture(s,'actual_waiting_cast');assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 starts=[e for e in events(s,'ability.started') if e['payload']['ability']=='ability/peer/wait'];assert starts and starts[0]['time']==29 and events(s,'peer.wait.impact')[0]['time']==32
 assert s.ctx.resources.current('waiter','hp')==101 and s.ctx.active('waiter') and s.ctx.get('waiter',('runtime','rebirth','count'))==1

def test_manual_command_while_waiting_cannot_borrow_owned_timer_lease():
 s=make();s.submit({'action':'skill','source':'waiter','ability':'ability/peer/wait'},at=10);s.advance(20);capture(s,'manual_wait_reject');assert not events(s,'peer.wait.impact') and any(e['type']=='command.rejected' and e['time']==10 for e in s.session.events)

def test_copied_real_buff_can_not_trigger_waiting_cast_before_actual_owned_timer():
 s=make();s.advance(2);b=deepcopy(s.ctx.get('waiter',('buffs','instances'))[0]);assert s.ctx.get('waiter',('runtime','rebirth','phase'))=='waiting';s.ctx.waiting_actions.trigger(b,'ability/peer/wait',None);s.advance(4);capture(s,'copied_buff_early_trigger');assert not events(s,'peer.wait.impact')
