"""Independent minimal DomainContext starts without a calculation cursor."""
from types import SimpleNamespace
import pytest
from tools.chapter09_joint_peer_v8.fixture import guard,START,REPORT,CORE
from ark_sim.kernel import Session
from ark_sim.domains.attributes import AttributeSystem
from ark_sim.rules.runtime import RuleRuntime
from ark_sim.contracts import thaw
import json

def minimal_attribute_rule(inputs,params,context):return inputs["base"] * 1.25

class PeerMinimalContext:
 def __init__(self):
  self.session=Session();self.program=SimpleNamespace(ruleset={'attribute_layers':['flat']});self.calls=0
  self.actor=self.session.world.create('unit/peer/minimal',{'attributes':{'base':{'atk':517},'modifiers':[]}})
  self.rules=RuleRuntime([{'id':'rule/peer/minimal','contract':'attributes.effective','implementation':{'type':'provider','provider':'peer.minimal_attribute'}}],bindings={'attributes.effective':'rule/peer/minimal'},providers={'peer.minimal_attribute':{'callable':minimal_attribute_rule,'version':'independent-1'}})
  self.attributes=AttributeSystem(self)
 def entity(self,ref):return self.session.world.get(ref)
 def calc(self,id,inputs,**kw):
  self.calls+=1;context={'time':self.session.time,'peer_attempt':self.calls,**kw.get('extra',{})};r=self.rules.evaluate(id,inputs,context=context)
  self.last_calculation_event_id=self.session.emit('calculation',{'calculation_id':id,'rule_id':r.rule_id,'value':r.value,'trace':r.trace,'peer_attempt':self.calls});return r.value

def test_domain_context_without_cursor_can_open_first_transaction_before_calculation():
 c=PeerMinimalContext();assert not hasattr(c,'last_calculation_event_id');before=c.session.checkpoint()
 with c.session.atomic():pass
 assert c.session.checkpoint()==before;assert not hasattr(c,'last_calculation_event_id');assert c.calls==0;assert guard()==START

def test_first_calculation_rollback_requires_fresh_evaluation_and_fresh_cause():
 c=PeerMinimalContext();assert not hasattr(c,'last_calculation_event_id');before=c.session.checkpoint();initial_view=c.entity(c.actor)
 with pytest.raises(RuntimeError,match='peer first calculation failure'):
  with c.session.atomic():
   assert c.attributes.value(c.actor,'atk')==646.25;assert c.calls==1;assert c.last_calculation_event_id==1;assert c.session.events[0]['payload']['peer_attempt']==1;raise RuntimeError('peer first calculation failure')
 assert c.session.checkpoint()==before;assert c.last_calculation_event_id is None;assert c.entity(c.actor) is not initial_view;assert c.attributes.cache=={}
 assert c.attributes.value(c.actor,'atk')==646.25;assert c.calls==2;assert len(c.session.events)==1;assert c.session.events[0]['type']=='calculation';assert c.session.events[0]['payload']['peer_attempt']==2
 assert c.attributes.value(c.actor,'atk')==646.25;assert c.calls==2;cached=thaw(c.session.events[-1]);assert cached['type']=='calculation.cached';assert cached['cause']==cached['payload']['source_event_id']==c.session.events[0]['id'];assert guard()==START
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'minimal_domain_cursor.json').write_text(json.dumps({'runtime':CORE,'without_cursor_before_first_atomic':True,'actual_rule_expression':'517 * 1.25','expected_value':646.25,'first_rolled_back_attempt':1,'fresh_recalculation_attempt':2,'fresh_cause_id':cached['cause'],'old_event_was_removed':True,'complete_kernel_rollback_equal':True,'World_view_rebound':True,'source_guard':True},indent=2),encoding='utf8')
