import sys
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT/'tools/experiments/m30_quota'))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
import test_quota as h
CORE='c77ce7a46101cf903fd9c6c56dcabddf5775008d091365cd7486ddeb47b8d740'
def make(p):
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';s=Engine.create(Compiler(providers=h.PROVIDERS).compile(p),seed=3701,providers=h.PROVIDERS);s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=0);return s
@pytest.mark.parametrize('outer_alias,nested_alias',[(False,True),(True,False),(True,True)])
def test_duplicate_ref_same_runtime_entity_inflight_and_history(outer_alias,nested_alias):
 p=h.fixture();p['projectiles'][0].update(max_hits=None,stop_after_first=False,can_hit_same_target=False);s=make(p);s.advance(1);source=s.ctx.projectiles._get('projectile/1');definition=s.program.definitions['projectile/probe'];original=s.ctx.effects.execute;results=[];entered=[False]
 def execute(owner,targets,effect,ability=None,cast=None,cause=None):
  if (cast or {}).get('projectile_impact') and not entered[0]:
   entered[0]=True;x=s.ctx.projectiles._get('projectile/1');results.append(s.ctx.projectiles._hit(x,definition,'a' if nested_alias else s.session.world.resolve('a')))
  return original(owner,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=execute;assert s.ctx.projectiles._hit(source,definition,'a' if outer_alias else s.session.world.resolve('a'));assert results==[False];assert s.ctx.resources.current('a','hp')==160 and s.ctx.projectiles._get('projectile/1')['hit_targets']==[s.session.world.resolve('a')];assert not s.ctx.projectiles._hit(source,definition,'a');assert s.ctx.projectiles._inflight_hits=={}
 # API reentrancy/canonicalization only; no command replay claim for manual hit.
@pytest.mark.parametrize('bad',['missing',-1,True,None])
def test_invalid_refs_error_before_quota_or_state_change(bad):
 p=h.fixture();p['projectiles'][0]['stop_after_first']=False;s=make(p);s.advance(1);before=s.checkpoint();x=s.ctx.projectiles._get('projectile/1')
 if bad is None:
  assert s.ctx.projectiles._hit(x,s.program.definitions['projectile/probe'],None);assert s.ctx.resources.current('a','hp')==160;return
 with pytest.raises((ValueError,KeyError,TypeError)):s.ctx.projectiles._hit(x,s.program.definitions['projectile/probe'],bad)
 assert s.checkpoint()==before and s.ctx.projectiles._inflight_hits=={}
def test_alias_valid_repeat_when_enabled_and_quota_two_exact():
 p=h.fixture();p['projectiles'][0].update(max_hits=2,stop_after_first=False,can_hit_same_target=True);s=make(p);s.advance(1);d=s.program.definitions['projectile/probe'];x=s.ctx.projectiles._get('projectile/1');assert s.ctx.projectiles._hit(x,d,'a');assert s.ctx.projectiles._hit(x,d,s.session.world.resolve('a'));assert not s.ctx.projectiles._hit(x,d,'a');assert s.ctx.resources.current('a','hp')==120 and s.ctx.projectiles._get('projectile/1')['hit_count']==2 and s.ctx.projectiles._inflight_hits=={}
def test_ordinary_public_command_reach_first_full_checkpoint_replay():
 s=make(h.fixture());s.advance(2);r=Engine.restore(s.program,s.checkpoint(),providers=h.PROVIDERS);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=h.PROVIDERS).snapshot();assert [(e['time'],e['payload']['amount']) for e in h.events(s,'damage.accepted')]==[(1,40)]
