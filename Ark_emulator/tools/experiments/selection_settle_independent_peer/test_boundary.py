from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.experiments.selection_settle_independent_peer.test_peer import fixture,L
INPUTS=[];CAPTURES=[]
def create(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=55555)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay()})
def source(p):return next(e for e in p['entities'] if L in e['id'])
def aid(p):return source(p)['components']['abilities'][0]
@pytest.mark.parametrize('value',[1,None,'true',[]])
def test_settle_activation_strict_bool_rejects_malformed_values(value):
 p=fixture(L);next(a for a in p['abilities'] if a['id']==aid(p))['activation']['settle_blocking']=value
 with pytest.raises(ValueError):Compiler().compile(p)
def test_standard_base_rule_failure_rolls_entire_prequery_settlement_back():
 p=fixture(L);p['rules'].append({'id':'rule/peer/fault_block','kind':'rule','contract':'blocking.eligibility','implementation':{'type':'graph','nodes':[{'id':'bad','expression':"{'accepted':1/0 > 0,'reason':'fault'}"}],'output':'nodes.bad'}});p['scenarioDraft']['rules']={'blocking.eligibility':'rule/peer/fault_block'}
 s=create(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('enemy',aid(p),automatic=True)
 assert s.checkpoint()==before;capture(s,'failed_settlement_atomic')
def test_declared_false_is_noopt_and_retains_known_unsettled_first_capture_policy():
 p=fixture(L);next(a for a in p['abilities'] if a['id']==aid(p))['activation']['settle_blocking']=False
 other=deepcopy(p['scenarioDraft']['initialEntities'][1]);other['instanceAlias']='other';other['position']={'row':2,'col':1};other['components']={'attributes':{'base':{'taunt_level':1000000000,'block_count':0}}};p['scenarioDraft']['initialEntities'].append(other)
 s=create(p);s.advance(1);cast=next(iter(s.ctx.get('enemy',('runtime','casts')).values()));capture(s,'explicit_false_noopt')
 assert cast['targets']==[s.session.world.resolve('other')]
def callback_fixture(kind):
 p=fixture(L);u=source(p)
 if kind=='nested':
  u['components']['abilities'].append('ability/peer/nested');p['abilities'].append({'id':'ability/peer/nested','kind':'ability','activation':{'mode':'manual'},'duration_seconds':1,'timeline':[{'at':7,'effect':{'op':'emit','target':'battle','event':'peer.nested'}}]})
  effect={'op':'trigger_ability','target':'source','ability':'ability/peer/nested'}
 else:effect={'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}
 p['buffs'].extend([{'id':'buff/peer/child','kind':'buff','on_remove':[effect]},{'id':'buff/peer/toggle','kind':'buff','toggle':{'rule':'rule/peer/held','buff':'buff/peer/child','initial_enabled':True,'restore_delay_seconds':1,'parameters':{},'events':[{'event':'blocking.changed','owner_role':'source'}]}}]);p['rules'].append({'id':'rule/peer/held','kind':'rule','contract':'passive.toggle','implementation':{'type':'expression','expression':'inputs.blocked_by != None'}});u['components']['buffs']={'initial':['buff/peer/toggle']}
 return p
def test_real_toggle_removal_source_retire_prevents_outer_cast_and_rolls_boundary_back():
 p=callback_fixture('retire');s=create(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.abilities.start('enemy',aid(p),automatic=True)
 assert s.checkpoint()==before;capture(s,'source_retire_atomic_reject')
def test_real_toggle_callback_nested_blocking_cast_must_not_be_overwritten_by_stale_runtime():
 p=callback_fixture('nested');s=create(p);before=s.checkpoint();rejected=False
 try:s.ctx.abilities.start('enemy',aid(p),automatic=True)
 except ValueError:rejected=True
 capture(s,'nested_cast_collision');assert rejected and s.checkpoint()==before
