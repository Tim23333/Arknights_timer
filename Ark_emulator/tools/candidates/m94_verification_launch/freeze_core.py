"""Freeze exact M94 core bytes after scoped current cases, no full-run claim."""
import json,hashlib,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(ROOT));from tools.candidates.m79_rebirth_environment.prepare import core,sha
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
def main():
 assert core(RUNTIME)==PIN
 v=OUT/'verification_current_run3.json';assert sha(v)=='f420e2cb105053ef96c2f9cf6314964b96a8c3714f60f8273e1a4c2ea377081b';r=json.loads(v.read_bytes());assert r['exitcode']==0 and len(r['cases'])==255
 m93=ROOT/'validation/campaign/m93_world_cast_leases/freeze.json';assert sha(m93)=='f855f5684de0a1b2e38a53ab054cb3dceef9d2b70755f61f9fe0a196384a1c29'
 before=r['guard_after'];source={}
 for p in sorted((RUNTIME/'ark_sim').rglob('*')):
  if p.is_file() and p.suffix in ('.py','.json'):assert before[str(p)]==sha(p);source[p.relative_to(RUNTIME).as_posix()]=sha(p)
 # The actual selected tests and verify_current.py have not changed. The stage
 # runner was revised after these cases solely to consume the compact plan.
 changed_tools=[name for name,pin in before.items() if sha(Path(name))!=pin]
 assert changed_tools==[str(ROOT/'tools/candidates/m94_complete_c4/verify_stage_public.py')],changed_tools
 archive=OUT/'source_files';dest=OUT/'freeze_core.json'
 if archive.exists() or dest.exists():raise ValueError('Preserve previous freeze')
 for name,pin in source.items():
  target=archive/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(RUNTIME/name,target);assert sha(target)==pin
 proofs=[v,m93,OUT/'composition.json',OUT/'composition_receipt.json',OUT/'stage_authoring.json',ROOT/'tools/candidates/m94_complete_c4/verify_current.py',Path(__file__)]
 report={'core':PIN,'source_files':source,'proofs':{str(p):sha(p) for p in proofs},'scoped_actual_passed':255,'after_case_incidental_tool_revision':changed_tools,'revision_note':'Only the separate unexecuted public stage runner changed to compact plan. Current-case runtime, catalog, verifier, tests and consumed helper/module files remain exact.','full_suite_status':'Separately running session19124, no inherited pass','baseline_status':'Separately running session22502, no inherited pass','whole_4_9_executed':False,'client_verified':False,'primary_promotion':False}
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':PIN,'source_files':len(source),'freeze_sha':sha(dest)}))
if __name__=='__main__':main()
