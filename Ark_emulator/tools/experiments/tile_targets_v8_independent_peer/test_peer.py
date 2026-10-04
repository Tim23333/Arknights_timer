from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.tile_targets_v7_independent_peer.test_peer import fixture
INPUTS=[];CAPTURES=[]
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=9808)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
@pytest.mark.parametrize('field,value',[('tile_targets',[{'row':0,'col':3}]),('generation',2),('ability','ability/fake')])
def test_actual_active_cast_captured_fields_tampering_is_rejected_without_writes(field,value):
 s=make(fixture(1));s.ctx.abilities.start('source','ability/peer/seal');cast=deepcopy(next(iter(s.ctx.get('source',('runtime','casts')).values())));cast[field]=value;ability=s.program.definitions['ability/peer/seal'];before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute('source',[],ability['timeline'][0]['effect'],ability=ability,cast=cast)
 assert s.checkpoint()==before;capture(s,'tampered_'+field)
def test_bool_generation_cannot_equal_integer_owned_cast_generation():
 s=make(fixture(1));s.ctx.abilities.start('source','ability/peer/seal');cast=deepcopy(next(iter(s.ctx.get('source',('runtime','casts')).values())));cast['generation']=True;ability=s.program.definitions['ability/peer/seal'];before=s.checkpoint();rejected=False
 try:s.ctx.effects.execute('source',[],ability['timeline'][0]['effect'],ability=ability,cast=cast)
 except ValueError:rejected=True
 capture(s,'bool_generation');assert rejected and s.checkpoint()==before
@pytest.mark.parametrize('reason',['death','control_interrupt'])
def test_sync_target_remove_callback_stops_owned_tile_cast_before_spawn_or_second_cell(reason,tmp_path):
 p=fixture(2);hero=next(d for d in p['definitions'] if d['id']=='unit/peer/hero');hero['components']['buffs']={'initial':['buff/peer/on_remove']}
 callback={'op':'retire','target':2,'parameters':{'reason':'withdrawn'}} if reason=='death' else {'op':'apply_buff','target':2,'buff':'buff/peer/stun'}
 p['definitions'].extend([{'id':'buff/peer/on_remove','kind':'buff','on_remove':[callback]},{'id':'buff/peer/stun','kind':'buff','selection_flags':{'abnormal_flags':[0]},'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True}}])
 s=make(p);s.submit({'action':'skill','source':'source','ability':'ability/peer/seal'},at=0);s.advance(3);h=write_ordered(tmp_path/'before.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'before.json',h));s.advance(5);r.advance(5)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'sync_'+reason)
 assert not s.ctx.alive('hero');assert s.ctx.get('source',('runtime','casts'))=={}
 assert s.ctx.active('source') is (reason!='death')
 assert not any(e['definition_id']=='unit/peer/token' for e in s.session.world.entities())
 assert len([e for e in s.session.events if e['type']=='instant_kill.executed'])==1
