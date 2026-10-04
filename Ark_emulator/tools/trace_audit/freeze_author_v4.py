"""Freeze V4 arithmetic identity subset with actual complete source-journal guards."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/author_freeze_v4'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);helpers=[ROOT/'tools/trace_audit'/n for n in ('stream_oracle_v4.py','stream_oracle_v4_math.py','stream_oracle_v4_identity.py','verify_wrapper_v4.py','capture_chen_wrapper_golden_v4.py','audit_sealed_c5_original_v2.py','body_binding_v1.py','audit_c5_source_bodies_v1.py')]+[ROOT/'tools/compare_campaign_trace.py'];record=[]
 for p in helpers:
  dst=OUT/'source'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);assert sha(p)==sha(dst);record.append({'path':str(p),'sha256':sha(p)})
 evidence=[]
 for folder in ('chen_wrapper_golden_v4','wrapper_tests_v4','root_negative_review_v4','root_binding_review_v4'):
  for p in (ROOT/'validation/trace_audit'/folder).glob('*'):
   if p.is_file():evidence.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
 for name in ('05-09.sealed_original_full.v3.json','05-09.sealed_original_full.v4.json','05-09.sealed_original.body_binding_v1.json'):
  p=ROOT/'validation/trace_audit'/name;evidence.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
 fullpath=ROOT/'validation/trace_audit/05-09.sealed_original_full.v4.json';full=json.loads(fullpath.read_bytes());assert full['source_formula_consistent'] and not full['all_fields_independently_verified'];assert full['all_consumed_source_before']==full['all_consumed_source_after']
 for path,pin in full['all_consumed_source_after'].items():assert sha(Path(path))==pin
 peers=[ROOT/'validation/trace_audit'/d/'verification.json' for d in ('root_negative_review_v4','root_binding_review_v4')];assert all(json.loads(p.read_bytes())['passed'] for p in peers);pinfile=ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json';evidence.append({'path':str(pinfile),'sha256':sha(pinfile),'bytes':pinfile.stat().st_size})
 result={'role':'V4 independent source-arithmetic/identity subset with full sealed trace; incomplete numerical coverage','helpers_all_local_imports':record,'source_standard_definition':{'path':str(ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate/ark_sim/content/presets/ark_standard.json'),'sha256':'1070ba6793cee5ded71c0f0b89a96ba72973d49989407e70a858a575febb9814'},'evidence':evidence,'complete_actual_journal':full['source_journal_reference'],'consumed_before':full['all_consumed_source_before'],'consumed_after':full['all_consumed_source_after'],'full1937246_trace_checked':True,'supported_formula_identity_counts':full['identity_counts'],'aggregate_provider_calls':full['aggregate_provider_calls_checked'],'verified_resource_transitions':full['verified_resource_transitions'],'independent_root9':True,'pending_fields':full['pending_fields'],'pending_categories_are_not_summed_into_global_accuracy':True,'old_v3_complete_false_positive_retained':True,'numeric_full_acceptance':False,'client_verified':False,'live_core_commands_helpers_registry_modified':False};dest=OUT/'freeze.json';dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'actual_root9':True,'numeric_full':False,'journal_actual_sha_verified':True}))
if __name__=='__main__':main()
