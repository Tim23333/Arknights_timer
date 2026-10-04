"""Freeze exact source-only capability plan and local helpers; no runtime claim."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter07_consumption_plan_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 plan=ROOT/'packages/campaign/chapter07_consumption_plan/source.consumption.plan.json';audit=OUT/'audit.json';p=json.loads(plan.read_bytes());assert sha(plan)=='298deaf0dc7ed9a1068d1dfe75c8b90a9e1c3f8ae0a967f3baa28ff3f87064f1';assert sha(audit)=='bc8daa3f5c751999df503cbeee665b28cf3365761777d5e44ce42b4a36105331';pins={n:h for n,h in p['source_inputs'].items()};pins[p['fixed_source_freeze']['path']]=p['fixed_source_freeze']['sha'];pins[p['known_interface_source_snapshot']['path']]=p['known_interface_source_snapshot']['sha'];assert all(sha(Path(n))==h for n,h in pins.items());helpers=[]
 for path in (ROOT/'tools/chapter07_consumption_plan').glob('*.py'):
  dest=OUT/'source'/path.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(path,dest);assert sha(path)==sha(dest);helpers.append({'path':str(path),'sha':sha(path)})
 result={'source_plan_sha':sha(plan),'source_audit_sha':sha(audit),'source_before':pins,'source_after':{n:sha(Path(n)) for n in pins},'helper_archives':helpers,'source_only':True,'runtime_or_stage_created':False,'client_verified':False};dest=OUT/'freeze.json';assert not dest.exists();dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'source_only':True}))
if __name__=='__main__':main()
