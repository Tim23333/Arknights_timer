"""Fresh optional substrate context; no Root/author fixture imports."""
from tools.chapter09_depletion_peer_joint_v3.fixture import CORE,CAND,ROOT,guard,START,REPORT,sha
from tools.chapter09_clock_peer_pillar_joint_v3.fixture import clock_scene,REG
from ark_sim import Compiler,Engine
from ark_sim.domains.attributes import AttributeSystem
from ark_sim.domains.resources import ResourceSystem
from ark_sim.domains.effects import EffectSystem
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.kernel import Session
from ark_sim.rules import RuleRuntime
from ark_sim.contracts import thaw,Intent
from types import SimpleNamespace
from collections.abc import Mapping
from copy import deepcopy
import json,pytest

class BareContext:
 def __init__(self,explicit_none=False):
  preset=json.loads((CAND/'ark_sim/content/presets/ark_standard.json').read_bytes());ruleset=deepcopy(preset['rulesets'][0]);ruleset['bindings']['damage.pipeline']='rule/peer/optional_fixed';self.program=SimpleNamespace(ruleset=ruleset);self.session=Session(quantum=.25);self.lifecycle=None
  if explicit_none:self.depletion=None
  fixed={'id':'rule/peer/optional_fixed','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'fixed','expression':"{'accepted': True, 'amount': 31, 'allocations': [], 'events': []}"}],'output':'nodes.fixed'}};self.rules=RuleRuntime(preset['rules']+[fixed],bindings=ruleset['bindings'],providers=BUILTIN_PROVIDERS);self.ref=self.session.world.create('unit/peer/bare',{'attributes':{'base':{'atk':531}},'resources':{'hp':{'current':109,'spec':{'initial':109,'capacity':109}}}});self.target=self.session.world.create('unit/peer/bare_target',{'resources':{'hp':{'current':83,'spec':{'initial':83,'capacity':83}}}});self.attributes=AttributeSystem(self);self.resources=ResourceSystem(self);self.effects=EffectSystem(self)
 def entity(self,r):return self.session.world.get(r)
 def get(self,r,path,default=None):
  v=self.entity(r)['components']
  for k in path:
   if not isinstance(v,Mapping) or k not in v:return default
   v=v[k]
  return thaw(v)
 def calc(self,name,inputs,**kw):
  out=self.rules.evaluate(name,inputs,scope={'component':kw.get('component',{}),'attribute_or_resource':kw.get('local',{}),'ability':(kw.get('ability') or {}).get('rules',{}),'effect':(kw.get('effect') or {}).get('rules',{})},rule_id=kw.get('rule_id'),context={'time':self.session.time,'seconds':self.session.time*self.session.quantum,**kw.get('extra',{})});value=thaw(out.value);self.last_calculation_event_id=self.session.emit('calculation',{'calculation_id':name,'value':value});return value
 def alive(self,r):return True
 def state(self):return self.get(self.ref,('peer_state',),{'finished':False})
 def state_update(self,**state):self.session.commit([Intent('set',self.ref,('peer_state',),state)])
 def health_resource(self,r):return 'hp'
 def emit(self,t,p,cause=None):return self.session.emit(t,p,cause=cause)
 def attribute_role(self,r):return {'attack':'atk','defense':'def','resistance':'res'}.get(r,r)
 def role_value(self,r,role):return self.attributes.value(r,self.attribute_role(role))

@pytest.mark.parametrize('explicit_none',[False,True])
def test_bare_optional_context_first_calculation_resource_damage_atomic_rollback(explicit_none):
 c=BareContext(explicit_none);assert not hasattr(c,'last_calculation_event_id');before=c.session.snapshot();cache=c.attributes.checkpoint_cache()
 with pytest.raises(RuntimeError,match='peer deliberate rollback'):
  with c.session.atomic():
   assert c.attributes.value(c.ref,'atk')==531;assert c.resources.adjust(c.ref,'hp',-7)==-7;c.effects.execute(c.ref,[c.target],{'op':'damage'});assert c.resources.current(c.ref,'hp')==102;assert c.resources.current(c.target,'hp')==52;raise RuntimeError('peer deliberate rollback')
 assert c.session.snapshot()==before;assert c.attributes.checkpoint_cache()==cache;assert c.last_calculation_event_id is None
 c.effects.execute(c.ref,[c.target],{'op':'damage'});assert c.resources.current(c.target,'hp')==52
 before=c.session.snapshot();cache=c.attributes.checkpoint_cache()
 for key in ['depletion_action','depletion_owned']:
  with pytest.raises(ValueError):c.effects.execute(c.ref,[c.target],{'op':'emit','event':'peer.fake_callback'},cast={key:{'owner':c.ref,'generation':73}})
  assert c.session.snapshot()==before and c.attributes.checkpoint_cache()==cache

def test_feature_absent_real_cast_owned_tag_cannot_dispatch_or_finish_or_emit():
 p=clock_scene();p['scenarioDraft']['commands']=[];s=Engine.create(Compiler(providers=REG).compile(p),providers=REG,seed=53183);assert s.ctx.depletion is None;s.ctx.abilities.start('worker','ability/peer/work');casts=s.ctx.get('worker',('runtime','casts'));cast_id,cast=next(iter(casts.items()));cast['depletion_owned']={'owner':s.session.world.resolve('worker'),'generation':73};s.ctx.set('worker',('runtime','casts',cast_id),cast);before=s.checkpoint()
 for kind in ['domain.ability.effect','domain.ability.finish']:
  task=next(t for t in s.session.scheduler.pending if t['kind']==kind and t['payload'].get('cast')==cast_id);s.session._handlers[kind](s.session,deepcopy(task['payload']));assert s.checkpoint()==before
 for key in ['depletion_action','depletion_owned']:
  with pytest.raises(ValueError):s.ctx.effects.execute('worker',['worker'],{'op':'emit','event':'peer.fake_callback'},cast={key:{'generation':73}})
  assert s.checkpoint()==before
 assert guard()==START
