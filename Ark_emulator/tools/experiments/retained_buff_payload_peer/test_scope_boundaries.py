from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from tools.experiments.retained_buff_payload_peer.test_peer import fixture,make,capture,fire,INPUTS
def test_impact_exception_rolls_back_packet_and_cleans_scopes_for_subsequent_forgery():
 p,forged=fixture();p['rules'][0]['implementation']['expression']="{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/launched','duration_seconds':True}]}"
 s=make(p);fire(s)
 with pytest.raises(ValueError):s.advance(10)
 assert not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
 assert s.ctx.resources.current('target','hp')==1000 and not s.ctx.get('target',('buffs','instances'),[])
 before=s.checkpoint();s.ctx.effects.execute('source',['target'],forged,cast={'projectile_impact':True,'id':'cast/2/1'});assert s.checkpoint()==before;capture(s,'exception_cleanup')
def test_equal_copy_of_actual_impact_cast_cannot_authorize_unlaunched_application():
 p,forged=fixture();p['rules'][0]['implementation']={'type':'provider','provider':'peer.copy_cast_probe'}
 state={};probes=[]
 def provider(inputs,params,context):
  s=state['sim'];scope=s.ctx.projectiles._impact_payload_scopes[-1];copy=deepcopy(scope['cast']);before=s.checkpoint();s.ctx.effects.execute('source',['target'],forged,cast=copy);probes.append({'value_equal':copy==scope['cast'],'identity_distinct':copy is not scope['cast'],'unchanged':before==s.checkpoint()})
  return {'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/launched','duration_seconds':1}]}
 registry={**BUILTIN_PROVIDERS,'peer.copy_cast_probe':provider};INPUTS.append(deepcopy(p));s=Engine.create(Compiler(registry=registry).compile(p),seed=62011);state['sim']=s;fire(s)
 try:s.advance(10)
 finally:capture(s,'equal_copy_cast')
 assert probes==[{'value_equal':True,'identity_distinct':True,'unchanged':True}]
 assert [x['definition'] for x in s.ctx.get('target',('buffs','instances'),[])]==['buff/peer/launched']
