"""Preserve old517 alias duplicate and numeric control before a new revision."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).parent));import test_quota_peer as t
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
OUT=ROOT/'validation/campaign/m30_roster_peer/alias_failure';OUT.mkdir(parents=True,exist_ok=True)
core=implementation_digest();assert core=='517290e56f59bdf5f57862dbadb8929b37cf6fbe0468116dcb39669df6357b51';rows=[]
for alias in (False,True):
 p=t.fixture(None,False,False);s=t.make(p);s.advance(1);original=s.ctx.effects.execute;observed=[]
 def nested(source,targets,effect,ability=None,cast=None,cause=None):
  if not observed and (cast or {}).get('projectile_impact'):
   observed.append('entered');x=s.ctx.projectiles._get('projectile/1');ref='a' if alias else s.session.world.resolve('a');observed.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],ref))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=nested;s.advance(1);rows.append({'nested_ref':'alias' if alias else 'numeric','fixture':t.INPUTS[-1],'observed':observed,'health':s.ctx.resources.current('a','hp'),'events':thaw(s.session.events),'snapshot':s.snapshot()})
assert rows[0]['health']==463 and rows[1]['health']==426
report={'core_start':core,'core_end':implementation_digest(),'scope':'synchronous _hit API instrumentation only, no publiccommand replay or stage claim','expected_same_target_alias_equivalent':True,'actual_numeric_health':463,'actual_alias_health':426,'cases':rows,'source_test_sha256':hashlib.sha256(Path(t.__file__).read_bytes()).hexdigest(),'formal_approved':False}
(OUT/'counterexample.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');(OUT/'test_quota_peer.py').write_bytes(Path(t.__file__).read_bytes());(OUT/'projectiles.py').write_bytes((t.RUNTIME/'ark_sim/domains/projectiles.py').read_bytes());print(json.dumps({'numeric_health':463,'alias_health':426,'source':core}))
