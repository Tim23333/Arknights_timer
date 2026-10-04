import json,hashlib
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture(delay=.2,ratio=.5,managed=False):
 spec={'resource':'hp','max_count':1,'delay_seconds':delay,'restore_ratio':ratio,'restore_rule':'rule/restore'}
 boss={'id':'unit/phoenix','kind':'entity','tags':['enemy'],'components':{'spatial':{},'attributes':{'base':{'max_hp':120,'atk':20,'def':0,'move_speed':1.3,'block_cost':1}},'resources':{'hp':{'initial':120,'capacity':120,'role':'health'},'sp':{'initial':0,'capacity':100,'recovery_rate':30}},'lifecycle':{'policy':'policy/ark_lifecycle'},'rebirth':spec}}
 hero={'id':'unit/shooter','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':200,'def':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'},'sp':{'initial':0,'capacity':10,'recovery_rule':'rule/event_sp','recovery':{'mode':'event','event':'damage.accepted','owner_role':'source','amount':1}}},'abilities':['ability/damage','ability/skip','ability/allow','ability/delayed_skip','ability/delayed_allow'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 abilities=[{'id':'ability/damage','kind':'ability','selector':'selector/boss','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}]
 for name,skip,at in [('skip',True,0),('allow',False,0),('delayed_skip',True,3),('delayed_allow',False,3)]:abilities.append({'id':'ability/'+name,'kind':'ability','selector':'selector/boss','activation':{'mode':'manual'},'timeline':[{'at':at,'effect':{'op':'instant_kill','parameters':{'cause':'script','skip_rebirth':skip}}}]})
 p={'manifest':{'requires':['preset/ark_standard']},'entities':[boss,hero],'rules':[{'id':'rule/event_sp','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.current + inputs.parameters.amount'}},{'id':'rule/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}}],'selectors':[{'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}],'abilities':abilities,'scenarioDraft':{'id':'scene/peer_rebirth','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'}}}
 if managed:
  p['scenarioDraft']['initialEntities']=[{'definition':'unit/shooter','instanceAlias':'hero','position':{'row':0,'col':0}}];p['scenarioDraft']['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'max_wait_seconds':-1,'fragments':[{'actions':[{'kind':'spawn','managed':True,'blocks_wave':True,'spawn':{'definition':'unit/phoenix','instanceAlias':'boss','position':{'row':1,'col':1}}}]}]}]}
 else:p['scenarioDraft']['initialEntities']=[{'definition':'unit/phoenix','instanceAlias':'boss','position':{'row':1,'col':1}},{'definition':'unit/shooter','instanceAlias':'hero','position':{'row':0,'col':0}}]
 return p

def create(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();data={'sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'seed':610031};INPUTS.append(data);return Engine.create(Compiler().compile(json.loads(raw)),seed=610031),data

def cmd(s,ability,at):s.submit({'action':'skill','source':'hero','ability':'ability/'+ability},at=at)
def ev(s,kind):return [e for e in s.session.events if e['type']==kind]
def exact(s,inputs,tmp,expected):
 h=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',h));s.advance(15);r.advance(15);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();CAPTURES.append({'input':inputs,'expected':expected,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay(),'checkpoint_sha256':h,'checkpoint_equal':True,'commands_replay_equal':True})


def test_managed_member_same_id_first_down_no_release_final_once(tmp_path):
 s,inputs=create(fixture(managed=True));cmd(s,'damage',1);cmd(s,'damage',8);s.advance(2);ref=s.session.world.resolve('boss');assert s.ctx.alive(ref) and not s.ctx.active(ref) and s.ctx.resources.current(ref,'hp')==0 and s.ctx.state()['kills']==0 and not ev(s,'combat.kill') and not ev(s,'timeline.member_released')
 sp=s.ctx.resources.current(ref,'sp');s.advance(4);assert s.ctx.resources.current(ref,'sp')==sp and s.ctx.resources.current(ref,'hp')==0
 exact(s,inputs,tmp_path,{'same_actor':ref,'due_at':7,'restore_hp':60,'final_death':8,'final_kills':1});assert s.session.world.resolve('boss')==ref and not s.ctx.alive(ref) and s.ctx.state()['kills']==1 and len(ev(s,'combat.kill'))==1 and len(ev(s,'timeline.member_released'))==1
 assert [(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted')]==[(1,120),(8,60)]
 assert len([e for e in ev(s,'entity.created') if e['payload']['definition']=='unit/phoenix'])==1


def test_zero_delay_preserves_full_damage_not_net_recovered_hp(tmp_path):
 s,inputs=create(fixture(delay=0));cmd(s,'damage',1);s.advance(2);assert s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==60 and not ev(s,'combat.kill') and ev(s,'damage.accepted')[0]['payload']['amount']==120
 exact(s,inputs,tmp_path,{'damage120':'before synchronous restore60','same_tick_rebirth':1,'damage_dealt':120});assert s.ctx.state()['damage_dealt']==120

@pytest.mark.parametrize('skip',[False,True])
def test_instant_kill_not_damage_or_attack_recovery(skip,tmp_path):
 s,inputs=create(fixture());cmd(s,'skip' if skip else 'allow',1);s.advance(2)
 assert not ev(s,'damage.accepted') and not ev(s,'attack.accepted') and s.ctx.resources.current('hero','sp')==0
 exact(s,inputs,tmp_path,{'skip_rebirth':skip,'damage_or_attack_events':0,'source_SP':0})
 assert s.ctx.state()['kills']==(1 if skip else 0) and len(ev(s,'combat.kill'))==(1 if skip else 0)

@pytest.mark.parametrize('skip',[False,True])
def test_pending_instantkill_retained_target_uses_management_semantics(skip,tmp_path):
 s,inputs=create(fixture());cmd(s,'delayed_skip' if skip else 'delayed_allow',0);cmd(s,'damage',1);s.advance(2);assert not s.ctx.active('boss')
 exact(s,inputs,tmp_path,{'pending_request_at':3,'skip':skip,'final_death_at3':skip})
 if skip:assert s.ctx.state()['kills']==1 and not s.ctx.alive('boss') and len(ev(s,'combat.kill'))==1 and not ev(s,'entity.rebirth.completed')
 else:assert s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==60 and len(ev(s,'instant_kill.rejected'))==1 and s.ctx.state()['kills']==0


def test_owner_scheduled_withdraw_cancels_pending_job_without_kill(tmp_path):
 p=fixture();p['entities'][0]['components']['rebirth']['on_begin']=[{'op':'schedule','delay_seconds':.1,'effect':{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}}]
 s,inputs=create(p);cmd(s,'damage',1);s.advance(2);assert any(t['kind']=='domain.rebirth.finish' for t in s.session.scheduler.pending)
 exact(s,inputs,tmp_path,{'withdraw_at':4,'final_kills':0,'no_recovery_afterwithdraw':True});assert not s.ctx.alive('boss') and s.ctx.state()['kills']==0 and not ev(s,'combat.kill') and len(ev(s,'entity.rebirth.cancelled'))==1 and not any(t['kind']=='domain.rebirth.finish' for t in s.session.scheduler.pending)


def test_on_begin_instantkill_has_one_final_kill_from_actual_executor(tmp_path):
 p=fixture();p['entities'][0]['components']['rebirth']['on_begin']=[{'op':'instant_kill','target':'source','parameters':{'cause':'callback','skip_rebirth':True}}]
 s,inputs=create(p);cmd(s,'damage',1);s.advance(2);exact(s,inputs,tmp_path,{'final_kills':1,'combat_kill_events':1,'actual_killer':'boss callback, not initiating damage source'})
 kills=ev(s,'combat.kill');assert s.ctx.state()['kills']==1 and len(kills)==1 and kills[0]['payload']['source']==s.session.world.resolve('boss')
