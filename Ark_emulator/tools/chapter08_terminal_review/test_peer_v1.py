from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.terminal_lifecycle import valid,buff_bound
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[];END='buff/peer/terminal_end';OTHER='buff/peer/other_remove'
def package(borrow=False,native=False):
 end_effects=[{'op':'instant_kill','target':'self','parameters':{'cause':'peer_source_end','skip_rebirth':False}}] if native else [{'op':'emit','event':'peer.end.removed'}]
 if borrow:end_effects=[{'op':'remove_buff','target':'self','buff':OTHER}]
 return {'schemaVersion':2,'manifest':{'id':'package/peer/terminal','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity*.5 if context.rebirth.count == 1 else 0'}}],'buffs':[{'id':END,'kind':'buff','duration_seconds':6/30,'on_remove':end_effects},{'id':OTHER,'kind':'buff','on_remove':[{'op':'instant_kill','target':'self','parameters':{'cause':'peer_noncompletion_end','skip_rebirth':False}}]}],'entities':[{'id':'unit/peer/boss','kind':'entity','components':{'attributes':{'base':{'max_hp':1000,'atk':31,'def':17,'mres':13}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/terminal','ability/peer/other'],'rebirth':{'resource':'hp','max_count':2,'delay_seconds':1/30,'restore_ratio':.5,'restore_rule':'rule/peer/restore','zero_restore_lifecycle':{'mode':'terminal_active','counts':[2],'duration_seconds':10/30,'owned_abilities':['ability/peer/terminal'],'retained_buffs':[END,OTHER],'completion_buffs':[END],'on_enter':[{'op':'apply_buff','target':'self','buff':END},{'op':'apply_buff','target':'self','buff':OTHER}]}}}},{'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/kill','ability/peer/trigger','ability/peer/foreign_remove']}}],'abilities':[{'id':'ability/peer/terminal','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'emit','event':'peer.terminal.packet'}}]},{'id':'ability/peer/other','kind':'ability','activation':{'mode':'manual'},'timeline':[]},{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'instant_kill','target':2,'parameters':{'cause':'peer_damage','skip_rebirth':False}}]},'timeline':[]},{'id':'ability/peer/trigger','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'trigger_ability','target':2,'ability':'ability/peer/terminal'}]},'timeline':[]},{'id':'ability/peer/foreign_remove','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'remove_buff','target':2,'buff':OTHER}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/terminal','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/boss','instanceAlias':'boss','position':{'row':0,'col':0}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':1}}]}}
def make(p=None):p=p or package();INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=8828000)
def command(s,name,at):s.submit({'action':'skill','source':'director','ability':'ability/peer/'+name},at=at)
def begin(s):command(s,'kill',1);command(s,'kill',3)
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def proof(s,tmp_path,end=16):
 s.advance(6);assert s.ctx.active('boss') and s.ctx.alive('boss') and s.ctx.resources.current('boss','hp')==0;pin=write_ordered(tmp_path/'terminal6.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'terminal6.json',pin));s.advance(end-6);r.advance(end-6);h=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()==h.checkpoint();return s
def ends(s):return [e for e in s.session.events if e['type']=='entity.terminal.completed']
def test_completion_without_native_kill_uses_real_fallback14_no_backdated_phase(tmp_path):
 s=make();begin(s);proof(s,tmp_path);capture(s,'fallback');assert [e['time'] for e in ends(s)]==[14] and ends(s)[0]['payload']['reason']=='deadline'
 assert len([e for e in s.session.events if e['type']=='entity.died'])==1
def test_genuine_completion_native_finish_callback_ends_at_its_expiry10_once(tmp_path):
 s=make(package(native=True));begin(s);proof(s,tmp_path);capture(s,'native_finish');assert [e['time'] for e in ends(s)]==[10] and ends(s)[0]['payload']['reason']=='owned_buff_finished' and len([e for e in s.session.events if e['type']=='entity.died'])==1
def test_noncompletion_nested_callback_cannot_borrow_outer_completion_scope_to_end_early(tmp_path):
 s=make(package(borrow=True));begin(s);proof(s,tmp_path);capture(s,'nested_borrow');assert [e['time'] for e in ends(s)]==[14]
def test_public_manual_and_foreign_trigger_need_actual_terminal_internal_authority(tmp_path):
 s=make();begin(s);s.submit({'action':'skill','source':'boss','ability':'ability/peer/terminal'},at=7);command(s,'trigger',8);proof(s,tmp_path);capture(s,'public_denial');assert len([e for e in s.session.events if e['type']=='command.rejected'])==2 and not any(e['type']=='peer.terminal.packet' for e in s.session.events) and [e['time'] for e in ends(s)]==[14]
def test_terminal_buffer_lease_boolean_generation_is_not_equivalent_to_one():
 s=make();begin(s);s.advance(6);inst=next(b for b in s.ctx.get('boss',('buffs','instances')) if b['definition']==END);assert buff_bound(s.ctx,2,inst);fake=deepcopy(thaw(inst));fake['generation']=True;assert not buff_bound(s.ctx,2,fake);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.rebirth.terminal_end(s.session,{'target':2,'generation':True})
 assert s.checkpoint()==before;capture(s,'bool')
