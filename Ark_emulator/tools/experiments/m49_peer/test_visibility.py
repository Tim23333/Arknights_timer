"""Independent arbitrary-name scenarios, never the author's fixture."""
import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def fixture():
 ghost={'id':'unit/secret','kind':'entity','tags':['enemy'],'rules':{'targeting.availability':'rule/available'},'components':{'spatial':{},'selection_state':{'side':1},'attributes':{'base':{'max_hp':1200,'atk':1,'def':0}},'resources':{'hp':{'initial':1200,'capacity':1200,'role':'health'},'gate':{'initial':0,'capacity':1}},'buffs':{'initial':['buff/switch']},'abilities':['ability/pulse','ability/hold','ability/release']}}
 hunter={'id':'unit/observer','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0},'attributes':{'base':{'max_hp':1000,'atk':120,'def':0}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'abilities':['ability/hit','ability/reveal']}}
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[ghost,hunter],
 'rules':[{'id':'rule/held','kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'inputs.owner.components.resources.gate.current == 1'}},{'id':'rule/available','kind':'rule','contract':'targeting.availability','parameters':{'blocked_flag':9},'implementation':{'type':'expression','expression':"params.blocked_flag not in inputs.selection_states.candidate.abnormal_flags or ('parameters' in inputs.selector and 'visibility_bypass_flags' in inputs.selector.parameters and params.blocked_flag in inputs.selector.parameters.visibility_bypass_flags)"}}],
 'buffs':[{'id':'buff/switch','kind':'buff','toggle':{'rule':'rule/held','buff':'buff/status','initial_enabled':True,'restore_delay_seconds':.2,'events':[{'event':'peer.pulse','owner_role':'target'}]}},{'id':'buff/status','kind':'buff','stacking':{'mode':'independent'},'selection_flags':{'abnormal_flags':[9]}},{'id':'buff/reveal','kind':'buff','duration_seconds':.1,'selection_flags':{'abnormal_immunes':[9]}}],
 'selectors':[{'id':'selector/hit','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1},{'id':'selector/reveal','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1,'parameters':{'visibility_bypass_flags':[9]}}],
 'abilities':[{'id':'ability/pulse','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'emit','target':'source','event':'peer.pulse'}]},'timeline':[]},{'id':'ability/hold','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':'source','resource':'gate','value':1}]},'timeline':[]},{'id':'ability/release','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':'source','resource':'gate','value':0}]},'timeline':[]},{'id':'ability/hit','kind':'ability','selector':'selector/hit','activation':{'mode':'manual','parameters':{'requires_targets':True},'on_start':[{'op':'damage','damage_type':'true'}]},'timeline':[]},{'id':'ability/reveal','kind':'ability','selector':'selector/reveal','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/reveal'}]},'timeline':[]}],
 'scenarioDraft':{'id':'scene/independent/visibility','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':4,'cols':5},'initialEntities':[{'definition':'unit/secret','instanceAlias':'secret','position':{'row':1,'col':1}},{'definition':'unit/observer','instanceAlias':'observer','position':{'row':3,'col':3}}]}}
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=4953)
def command(s,name,at,source='secret'):s.submit({'action':'skill','source':source,'ability':'ability/'+name},at=at)
def flags(s):
 from ark_sim.domains.selection import DEFAULT_STATE
 return s.ctx.spatial.selection_state('secret',DEFAULT_STATE)['abnormal_flags']
def test_query_is_pure_and_toggle_parameters_are_not_native_id_branches():
 s=make();before=s.checkpoint();assert s.ctx.spatial.eligible('observer','selector/hit')==[];assert s.checkpoint()==before
 assert flags(s)==[9];command(s,'pulse',2);command(s,'hit',7,'observer');command(s,'hit',8,'observer');s.advance(10)
 assert s.ctx.resources.current('secret','hp')==1080 and [e['time'] for e in s.session.events if e['type']=='command.rejected']==[8]
def test_pulse_restart_deadline_public_ordered_disk_replay(tmp_path):
 s=make();command(s,'pulse',2);command(s,'pulse',5);command(s,'hit',10,'observer');command(s,'hit',11,'observer');s.advance(7)
 path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(7);r.advance(7)
 assert s.ctx.resources.current('secret','hp')==1080 and flags(s)==[9] and s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_held_rule_prevents_early_restore_until_actual_release():
 s=make();command(s,'hold',2);command(s,'pulse',3);command(s,'release',7);command(s,'hit',12,'observer');command(s,'hit',13,'observer');s.advance(15)
 assert s.ctx.resources.current('secret','hp')==1080 and [e['time'] for e in s.session.events if e['type']=='command.rejected']==[13]
def test_live_immunity_preserves_underlying_child_and_never_removes_camouflage():
 p=fixture();p['buffs'][1]['selection_flags']['abnormal_flags']=[9,17];s=make(p);command(s,'reveal',2,'observer');command(s,'hit',4,'observer');command(s,'hit',5,'observer');s.advance(7)
 assert flags(s)==[9,17] and s.ctx.resources.current('secret','hp')==1080
 # This selector uses only availability; the independent projection retains17.
 assert any(i['definition']=='buff/status' for i in s.ctx.get('secret',('buffs','instances')))
def test_parent_expiry_before_restore_cannot_recreate_child():
 p=fixture();p['buffs'][0]['duration_seconds']=.1;s=make(p);command(s,'pulse',1);s.advance(12)
 assert not s.ctx.get('secret',('buffs','instances')) and flags(s)==[]
def test_real_child_callback_rng_and_failure_restore_guards_and_every_checkpoint_value():
 p=fixture();p['rules'].append({'id':'rule/fail','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}});p['buffs'][1]['on_remove']=[{'op':'random','stream':'peer','probability':1,'on_success':[{'op':'modify_resource','target':'source','resource':'gate','amount_rule':'rule/fail'}]}]
 s=make(p);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.effects.execute('secret',['secret'],{'op':'emit','event':'peer.pulse'})
 assert s.checkpoint()==before and not s.ctx.buffs.toggles._busy and not s.ctx.buffs.toggles._requested and not s.ctx.buffs.toggles._removing
def test_two_controller_children_remain_separate_when_one_parent_removed():
 p=fixture();p['buffs'].append({**deepcopy(p['buffs'][0]),'id':'buff/switch2'});p['entities'][0]['components']['buffs']['initial'].append('buff/switch2');s=make(p)
 parents=[i for i in s.ctx.get('secret',('buffs','instances')) if i['definition'].startswith('buff/switch')];children=[i for i in s.ctx.get('secret',('buffs','instances')) if i['definition']=='buff/status'];assert len(children)==2 and len({i['toggle_parent'] for i in children})==2
 s.ctx.buffs.remove('secret',parents[0]['id']);assert len([i for i in s.ctx.get('secret',('buffs','instances')) if i['definition']=='buff/status'])==1 and flags(s)==[9]
@pytest.mark.parametrize('change',[lambda p:p['buffs'][0]['toggle'].update(rule='rule/available'),lambda p:p['buffs'][0]['toggle']['events'][0].update(owner_role='owner')])
def test_invalid_interface_references_compile_reject(change):
 p=fixture();change(p)
 with pytest.raises(ValueError):Compiler().compile(p)
