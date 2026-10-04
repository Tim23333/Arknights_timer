from pathlib import Path
from copy import deepcopy
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2];PROFILE=ROOT/'packages/campaign/chapter08_consumers/flame/loop.profile.v3.json';INPUTS=[];CAPTURES=[]
def package():
 profile=json.loads(PROFILE.read_bytes());initial=deepcopy(profile['initial_entities'])
 for item in initial:item['definition']='unit/peer/dummy_flame'
 initial.append({'definition':'unit/peer/controller','instanceAlias':'controller','position':{'row':0,'col':0}})
 return {'schemaVersion':2,'manifest':{'id':'package/peer/native_flame_loop','requires':['preset/ark_standard']},'buffs':[{'id':'buff/peer/device25','kind':'buff','duration_seconds':25,'on_remove':[{'op':'retire','target':'self','parameters':{'reason':'withdrawn'}}]}],'entities':[{'id':'unit/peer/dummy_flame','kind':'entity','components':{'spatial':{},'attributes':{'base':{'max_hp':100,'atk':0,'def':0,'mres':0}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'buffs':{'initial':['buff/peer/device25']},'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/controller','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/next']}}],'abilities':[{'id':'ability/peer/next','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'advance_branch','parameters':{'branch':'bsnake_flame'}}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/loop','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':9,'cols':13},'branches':profile['runtime_branch'],'initialEntities':initial}}
def make():p=package();INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=88721)
def command(s,index):s.submit({'action':'skill','source':'controller','ability':'ability/peer/next'},at=index*780)
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def test_native_loop_eighth_phase_wrap_third_traverse_exact105_budget_with_real25s_dummy_devices_cp_head(tmp_path):
 s=make()
 for index in range(21):command(s,index)
 s.advance(6200);pin=write_ordered(tmp_path/'loop6200.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'loop6200.json',pin));s.advance(10151);r.advance(10151);h=replay(s.program,s.export_replay());capture(s,'loop21');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 phases=[e['payload']['phase_index'] for e in s.session.events if e['type']=='branch.phase_finished'];assert phases==list(range(7))*3 and phases[7]==0 and phases[14]==0
 registry=s.ctx.state()['predefined_reactivation'];assert sum(row['activations'] for row in registry.values())==105 and all(row['activations']==row['profile']['max_activations'] for row in registry.values())
 source=json.loads(PROFILE.read_bytes());expected=source['native_phase_keys'];actions=[e for e in s.session.events if e['type']=='entity.activated'];assert len(actions)==105 and [e['payload']['registration_key'] for e in actions]==sum(expected*3,[])
 assert all(not s.ctx.active(row['current']) for row in registry.values()) and not s.ctx.state().get('finished',False)
def test_22nd_over_ceiling_request_reports_failure_not_fake_branch_completion():
 s=make()
 for index in range(22):command(s,index)
 with pytest.raises(ValueError,match='budget exhausted'):s.advance(16381)
 capture(s,'ceiling_failure');assert not s.ctx.state().get('finished',False) and len([e for e in s.session.events if e['type']=='branch.phase_finished'])==21
 assert sum(row['activations'] for row in s.ctx.state()['predefined_reactivation'].values())==105



