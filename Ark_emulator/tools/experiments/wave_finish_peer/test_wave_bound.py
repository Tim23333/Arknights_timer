from copy import deepcopy
from pathlib import Path
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
ROOT=Path(__file__).resolve().parents[3]
def finish():return {'op':'finish_timeline_wave','target':'source','parameters':{'finish_and_skip':False,'track_source_at_next_wave':False,'track_source_wave_delta':0,'track_all_managed_at_next_wave':False}}
def spawn(alias,t=0,fragment=False):return {'kind':'spawn','delay_seconds':t/30,'managed':True,'blocks_wave':True,'blocks_fragment':fragment,'spawn':{'definition':'unit/w/owner','instanceAlias':alias,'position':{'row':0,'col':0}}}
def wave(actions,pre=0,post=0):return {'pre_delay_seconds':pre/30,'post_delay_seconds':post/30,'max_wait_seconds':-1,'fragments':[{'pre_delay_seconds':0,'actions':actions}]}
def package():return {'schemaVersion':2,'manifest':{'id':'package/peer/wave','requires':['preset/ark_standard']},'abilities':[{'id':'ability/w/finish','kind':'ability','activation':{'mode':'manual','on_start':[finish()]},'timeline':[]}],'entities':[{'id':'unit/w/owner','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':127,'atk':13,'def':31,'mres':17}},'resources':{'hp':{'initial':127,'capacity':127,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/w/finish'],'spatial':{}}}],'scenarioDraft':{'id':'scene/wave_peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[wave([spawn('first'),spawn('delayed',7)],post=3),wave([spawn('next')],pre=2)]}}}
def make(p=None):p=p or package();INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=7074)
def capture(s,k):CAPTURES.append({'case':k,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'commands':s.export_replay()})
def ev(s,k):return [e for e in s.session.events if e['type']==k]
def test_public_finish_preserves_pending_birth_post_pre_and_cp_head(tmp_path):
 s=make();s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=1);s.advance(2);assert s.ctx.state()['timeline']['remaining_actions']==1 and s.ctx.state()['pending_waves']==2
 pin=write_ordered(tmp_path/'wave2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'wave2.json',pin));s.advance(12);r.advance(12);h=replay(s.program,s.export_replay());capture(s,'futurebirths')
 assert s.checkpoint()==r.checkpoint()==h.checkpoint();assert len(ev(s,'timeline.finish_requested'))==1
 born={e['payload']['target']:e['time'] for e in ev(s,'entity.created')};assert born[s.session.world.resolve('delayed')]==7 and born[s.session.world.resolve('next')]==12
 assert all(s.ctx.alive(x) and s.ctx.resources.current(x,'hp')==127 for x in ['first','delayed','next']) and s.ctx.state()['kills']==s.ctx.state()['leaks']==0
def test_late_old_member_never_finishes_new_wave_or_repeats_original():
 s=make();s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=1);s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=2);s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=13);s.advance(16);capture(s,'late_oldmember');assert len(ev(s,'timeline.finish_requested'))==1 and any(e['time']==13 for e in ev(s,'timeline.finish_rejected')) and s.ctx.state()['timeline']['wave_index']==1
def test_nonmanaged_initial_owner_cannot_release_currentwave():
 p=package();p['scenarioDraft']['initialEntities']=[{'definition':'unit/w/owner','instanceAlias':'unmanaged','position':{'row':0,'col':1}}];s=make(p);s.submit({'action':'skill','source':'unmanaged','ability':'ability/w/finish'},at=1);s.advance(15);capture(s,'not_managed');assert not ev(s,'timeline.finish_requested') and s.ctx.state()['timeline']['wave_index']==0
def test_fragmentblock_is_not_skipped_by_wavefinish():
 p=package();p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['blocks_fragment']=True;s=make(p);s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=1);s.advance(16);capture(s,'fragmentblock');assert len(ev(s,'timeline.finish_requested'))==1 and s.ctx.state()['timeline']['phase']=='fragment_wait' and s.ctx.state()['timeline']['wave_index']==0
@pytest.mark.parametrize('key,value',[('finish_and_skip',True),('finish_and_skip',0),('track_source_wave_delta',False),('track_source_wave_delta',-1),('track_source_wave_delta',float('nan'))])
def test_unimplemented_or_wrongtype_finish_flags_failclosed_compile(key,value):
 p=package();p['abilities'][0]['activation']['on_start'][0]['parameters'][key]=value;INPUTS.append(p)
 with pytest.raises(ValueError):Compiler().compile(p)
def test_missing_timeline_compile_rejected():
 p=package();p['scenarioDraft'].pop('timeline');p['scenarioDraft']['initialEntities']=[{'definition':'unit/w/owner','instanceAlias':'a','position':{'row':0,'col':0}}];INPUTS.append(p)
 with pytest.raises(ValueError):Compiler().compile(p)
def test_late_bad_pipeline_rolls_back_finish_request_and_hp():
 p=package();p['rules']=[{'id':'rule/w/bad','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'bad','expression':'1/0'}],'output':'nodes.bad'}}];p['abilities'][0]['activation']['on_start']=[{'op':'modify_resource','target':'source','resource':'hp','delta':-3},finish(),{'op':'damage','target':'source','damage_type':'true','rules':{'damage.pipeline':'rule/w/bad'}}];s=make(p);s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=1);s.advance(1)
 s.advance(1);assert ev(s,'command.rejected')
 capture(s,'late_callback_fault');assert s.ctx.resources.current('first','hp')==127 and not ev(s,'timeline.finish_requested') and not s.ctx.state()['timeline'].get('finish_requests')
def test_control_ack_gate_remains_when_enemies_released():
 p=package();p['controls']=[{'id':'control/w/story','kind':'control','clock_policy':'logical','ack_policy':'external','steps':[{'kind':'ack','key':'continue'}]}];p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append({'kind':'control','definition':'control/w/story','instanceAlias':'story','managed':True,'blocks_wave':True,'blocks_fragment':False})
 s=make(p);s.submit({'action':'skill','source':'first','ability':'ability/w/finish'},at=1);s.advance(14);assert s.ctx.state()['timeline']['wave_index']==0 and s.ctx.controls.instance('story')['status']=='running';s.submit({'action':'control_ack','control':'story','step':0},at=15);s.advance(7);capture(s,'real_story_gate');assert s.ctx.controls.instance('story')['status']=='completed' and s.ctx.state()['timeline']['wave_index']==1
