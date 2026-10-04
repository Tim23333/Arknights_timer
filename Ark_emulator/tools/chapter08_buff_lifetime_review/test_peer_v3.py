from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.domains.providers import BUILTIN_PROVIDERS
INPUTS=[];CAPTURES=[]
def invalid_provider(inputs,params,context):return {'bool':True,'negative':-1,'nan':float('nan'),'infinity':float('inf')}[params['code']]
REGISTRY={**BUILTIN_PROVIDERS,'peer.invalid_rate':{'callable':invalid_provider,'version':'1'}}
def package(mode='refresh'):
 return {'schemaVersion':2,'manifest':{'id':'package/peer/lifetime','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/rate','kind':'rule','contract':'buff.lifetime_rate','implementation':{'type':'expression','expression':'inputs.attributes.clock_rate'}}],'buffs':[{'id':'buff/peer/timer','kind':'buff','duration_seconds':6/30,'interval_seconds':2/30,'lifetime':{'rule':'rule/peer/rate','parameters':{},'count_when_inactive':True},'stacking':{'mode':mode},'modifiers':[{'attribute':'atk','layer':'flat','value':17}],'effects':[{'op':'emit','event':'peer.timer.packet'}]},{'id':'buff/peer/fast','kind':'buff','modifiers':[{'attribute':'clock_rate','layer':'flat','value':1}]},{'id':'buff/peer/pause','kind':'buff','modifiers':[{'attribute':'clock_rate','layer':'flat','value':-1}]},{'id':'buff/peer/invalid','kind':'buff','modifiers':[{'attribute':'clock_rate','layer':'flat','value':-2}]}],'entities':[{'id':'unit/peer/owner','kind':'entity','components':{'attributes':{'base':{'max_hp':1000,'atk':31,'def':13,'mres':17,'clock_rate':1}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/install','ability/peer/fast','ability/peer/pause','ability/peer/unpause','ability/peer/remove','ability/peer/replace','ability/peer/invalid']}}],'abilities':[{'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':effects},'timeline':[]} for name,effects in [('install',[{'op':'apply_buff','target':2,'buff':'buff/peer/timer'}]),('fast',[{'op':'apply_buff','target':2,'buff':'buff/peer/fast'}]),('pause',[{'op':'apply_buff','target':2,'buff':'buff/peer/pause'}]),('unpause',[{'op':'remove_buff','target':2,'buff':'buff/peer/pause'}]),('remove',[{'op':'remove_buff','target':2,'buff':'buff/peer/timer'}]),('replace',[{'op':'remove_buff','target':2,'buff':'buff/peer/timer'},{'op':'apply_buff','target':2,'buff':'buff/peer/timer'}]),('invalid',[{'op':'apply_buff','target':2,'buff':'buff/peer/invalid'}])]],'scenarioDraft':{'id':'scene/peer/lifetime','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/owner','instanceAlias':'owner','position':{'row':0,'col':0}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':1}}]}}
def make(p=None):p=p or package();INPUTS.append(deepcopy(p));return Engine.create(Compiler(providers=REGISTRY).compile(p),providers=REGISTRY,seed=818300)
def command(s,name,at):s.submit({'action':'skill','source':'director','ability':'ability/peer/'+name},at=at)
def timers(s):return [b for b in s.ctx.get('owner',('buffs','instances'),[]) if b['definition']=='buff/peer/timer']
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def equality(s,tmp_path,split,end):
 s.advance(split);pin=write_ordered(tmp_path/'lifetime.cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'lifetime.cp.json',pin),providers=REGISTRY);s.advance(end-split);r.advance(end-split);h=replay(s.program,s.export_replay(),providers=REGISTRY);assert s.checkpoint()==r.checkpoint()==h.checkpoint();return s
def removed(s):return [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']=='buff/peer/timer']
def packets(s):return [e['time'] for e in s.session.events if e['type']=='peer.timer.packet']
def test_rate_change_consumes_previous_interval_before_new_rate_no_packet_at_expiry(tmp_path):
 s=make();command(s,'install',0);command(s,'fast',2);equality(s,tmp_path,3,7);capture(s,'fast');assert removed(s)==[4] and packets(s)==[2] and not timers(s)
def test_zero_rate_pause_then_resume_keeps_periodic_cadence_and_nominal_remaining(tmp_path):
 s=make();command(s,'install',0);command(s,'pause',2);command(s,'unpause',5);equality(s,tmp_path,4,11);capture(s,'pause');assert removed(s)==[9] and packets(s)==[2,4,6,8]
@pytest.mark.parametrize('mode,expiry,expected',[('refresh',9,[2,5,7]),('extend',12,[2,5,7,9,11])])
def test_reapplication_modes_restart_owned_callback_and_distinguish_remaining_time(mode,expiry,expected,tmp_path):
 s=make(package(mode));command(s,'install',0);command(s,'install',3);equality(s,tmp_path,4,14);capture(s,mode);assert removed(s)==[expiry] and packets(s)==expected
def test_remove_reapply_new_uid_does_not_accept_old_callback(tmp_path):
 s=make();command(s,'install',0);command(s,'replace',3);s.advance(3);old=timers(s)[0];s.advance(1);assert timers(s)[0]['id']!=old['id'];before=s.checkpoint();s.ctx.buffs.lifetime(s.session,{'target':2,'instance':old['id'],'generation':old['generation']});assert s.checkpoint()==before
 pin=write_ordered(tmp_path/'replace4.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'replace4.json',pin),providers=REGISTRY);s.advance(8);r.advance(8);h=replay(s.program,s.export_replay(),providers=REGISTRY);capture(s,'replace');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and removed(s)==[3,9] and packets(s)==[2,5,7]
def test_direct_forged_current_timer_without_dispatch_authority_is_noop():
 s=make();command(s,'install',0);s.advance(2);b=timers(s)[0];before=s.checkpoint();s.ctx.buffs.lifetime(s.session,{'target':2,'instance':b['id'],'generation':b['generation']});capture(s,'forged');assert s.checkpoint()==before
@pytest.mark.parametrize('bad',['bool','negative','nan','infinity'])
def test_invalid_rate_output_rolls_back_apply_allocation_tasks_and_trace(bad):
 p=package();p['rules'][0]['implementation']={'type':'provider','provider':'peer.invalid_rate'};p['rules'][0]['parameters']={'code':bad};s=make(p);s.advance(1);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.buffs.apply('director','owner','buff/peer/timer')
 capture(s,'invalid_rate');assert s.checkpoint()==before
def test_nonpositive_resolved_duration_cannot_install_owned_clock():
 s=make();s.advance(1);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.buffs.apply('director','owner','buff/peer/timer',duration_override=0)
 capture(s,'duration0');assert s.checkpoint()==before
def test_exact_expiry_visibility_before_callback_and_same_tick_pause_does_not_resurrect(tmp_path):
 p=package();p['buffs'][0]['control']={'attack':False};s=make(p);command(s,'install',0);command(s,'pause',6);s.advance(6)
 assert timers(s) and s.ctx.buffs.controls('owner')['attack'] is True
 pin=write_ordered(tmp_path/'expiry6.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'expiry6.json',pin),providers=REGISTRY);s.advance(2);r.advance(2);h=replay(s.program,s.export_replay(),providers=REGISTRY);capture(s,'expiry6');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and removed(s)==[6] and packets(s)==[2,4]
def test_inactive_dormant_owner_does_not_consume_before_actual_activation(tmp_path):
 p=package();p['buffs'][0]['lifetime']['count_when_inactive']=False;p['buffs'][0]['removal']={'on_target_death':'retain'};p['entities'][0]['components']['buffs']={'initial':['buff/peer/timer']};p['scenarioDraft']['initialEntities'][0].update(active=False,registration_key='peer_dormant')
 p['entities'][1]['components']['abilities'].append('ability/peer/activate');p['abilities'].append({'id':'ability/peer/activate','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'activate_predefined','target':'battle','parameters':{'key':'peer_dormant'}}]},'timeline':[]})
 s=make(p);command(s,'activate',5);equality(s,tmp_path,3,13);capture(s,'dormant');assert removed(s)==[11]
def test_source_retirement_retained_timer_keeps_actual_owner_clock_and_cleanup(tmp_path):
 p=package();p['entities'][1]['components']['abilities'].append('ability/peer/leave');p['abilities'].append({'id':'ability/peer/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'self','parameters':{'reason':'peer_retire'}}]},'timeline':[]})
 s=make(p);command(s,'install',0);command(s,'leave',3);equality(s,tmp_path,2,8);capture(s,'source_retire');assert removed(s)==[6] and packets(s)==[2,4] and not s.ctx.active('director')
def test_expiry_on_remove_fault_restores_buff_clock_uid_world_events_rng():
 p=package();p['buffs'][0]['on_remove']=[{'op':'emit','event':'peer.before_fault'},{'op':'modify_resource','resource':'absent','amount':1}];s=make(p);command(s,'install',0);s.advance(6);before=s.checkpoint()
 with pytest.raises(Exception):s.advance(1)
 after=s.checkpoint();capture(s,'remove_fault')
 assert before['kernel']['world']==after['kernel']['world'] and before['kernel']['random']==after['kernel']['random'] and before['kernel']['events']==after['kernel']['events']
