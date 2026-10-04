import hashlib,json,runpy,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from ark_sim.adapters.api import implementation_digest
PIN='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'}]
paths.extend(ROOT/p for p in ['tools/verify_v2_baseline.py','packages/ark_content/level_main_00_01.json','packages/custom/custom_guard.json','scenarios/level_main_00_01/commands.json'])
guards={str(p):sha(p) for p in paths};start=time.monotonic();out=ROOT/'validation/campaign/chapter06_buff_join_v9/baseline_v9.json'
if out.exists():raise FileExistsError('Preserve baseline')
sys.argv=[str(ROOT/'tools/verify_v2_baseline.py'),'--output',str(out)]
runpy.run_path(str(ROOT/'tools/verify_v2_baseline.py'),run_name='__main__')
assert implementation_digest()==PIN and guards=={str(p):sha(p) for p in paths}
target=out.with_name('baseline_v9_guard.json')
with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':0,'elapsed_seconds':time.monotonic()-start,'guards':guards,'baseline_sha':sha(out),'full_stage_executed':False},f,indent=2)
print(json.dumps({'sha':sha(target),'exitcode':0}))
