import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).parent));from test_peer import fixture,make,events,RUNTIME
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/m76_catalog_peer';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=implementation_digest();files={str(p.relative_to(RUNTIME)):sha(p) for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']}
p=fixture();specs=p['entities'][0]['components']['lifecycle']['death_projectiles'];specs.append(json.loads(json.dumps(specs[0])));s=make(p);old=s.ctx.buffs.toggles.pulse;seen=[]
def pulse(event,payload):
 old(event,payload)
 if event=='projectile.launched' and not seen:
  seen.append(True);s.ctx.lifecycle.retire('slime','withdrawn')
s.ctx.buffs.toggles.pulse=pulse;s.advance(3);after=implementation_digest();assert before==after
report={'schema':'ark-sim/independent-boundary-counterexample/v1','status':'failed_expected_single_after_source_retirement','core_before':before,'core_after':after,'actual_module':sys.modules['ark_sim'].__file__,'source_before':files,'source_after':{str(p.relative_to(RUNTIME)):sha(p) for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']},'helper_sha256':sha(Path(__file__)),'test_sha256':sha(Path(__file__).with_name('test_peer.py')),'input':p,'commands':s.export_replay(),'snapshot':s.snapshot(),'expected_launch_count':1,'actual_launch_count':len(events(s,'projectile.launched')),'actual_kills':s.ctx.state()['kills'],'actual_source_state':s.ctx.get('slime',('runtime','state')),'scope':'Legal two death-emission specs; synchronous launch callback calls real lifecycle.retire withdrawn. Public original death command. Instrumented callback scope, not falsely claimed command-only reproduction. Single-source bslime spec not claimed independently affected.','client_verified':False}
assert report['source_before']==report['source_after'];out=OUT/'multiple_emission_source_withdraw.counterexample.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(sha(out))
