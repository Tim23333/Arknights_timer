"""Freeze three reviewed added formulas; unverified categories remain explicit."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/author_freeze_v5'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);helpers=[ROOT/'tools/trace_audit'/name for name in ('stream_oracle_v5.py','stream_oracle_v5_math.py','stream_oracle_v5_identity.py','prepare_simple_formulas_v5.py','verify_simple_v5.py','audit_sealed_05_09_v5.py','root_simple_rules_v5.py')]+[ROOT/'tools/compare_campaign_trace.py'];archives=[]
 for p in helpers:
  dest=OUT/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(p)==sha(dest);archives.append({'path':str(p),'sha256':sha(p)})
 fullpath=ROOT/'validation/trace_audit/05-09.sealed_original_full.v5.json';full=json.loads(fullpath.read_bytes());assert full['source_formula_consistent'] and not full['all_fields_independently_verified'] and full['consumed_before']==full['consumed_after'];assert all(sha(Path(p))==h for p,h in full['consumed_after'].items());peerdir=ROOT/'validation/trace_audit/root_simple_rules_v5';peer=peerdir/'verification.json';r=json.loads(peer.read_bytes());assert r['passed'];evidence=[]
 for directory in (ROOT/'validation/trace_audit/simple_formulas_v5',peerdir,ROOT/'validation/trace_audit/root_negative_review_v5',ROOT/'validation/trace_audit/root_binding_review_v5'):
  for p in directory.glob('*'):
   if p.is_file():evidence.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
 result={'role':'Three added standard-source formula subset with independent peer; not all numerical accuracy','helpers_all_local_imports':archives,'evidence':evidence,'full_sealed_proof':{'path':str(fullpath),'sha256':sha(fullpath),'journal':full['source_journal_reference'],'before':full['consumed_before'],'after':full['consumed_after'],'identity_counts':full['identity_counts']},'added_formulas':{'rule/ark_time_quantize':{'actual_appearances':36484,'scope':'ceil(round(seconds/quantum,12)), exact float ratio then integer ceil; no client rounding assumption beyond pinned standard source'},'rule/ark_ability_windup':{'actual_appearances':233,'scope':'Standard source static direct return of captured timing_parameters.seconds only. Custom source animation/variable windup formulas remain unverified.'},'rule/ark_deploy_refund':{'actual_appearances':11,'scope':'Paid cost times captured ratio with optional declared native raw_cost cap; source cap/bounds verification remains separate'}},'independent_new_formula_peer':{'path':str(peer),'sha256':sha(peer),'cases':11,'actual_exit':0,'scope':'5 independent quantization literals, windup/refund/cap literals and 3 real-input mutations; not whole client accuracy'},'inherited_identity9_scope_separate':True,'pending_fields':full['pending_fields'],'pending_categories_never_summed_as_global_accuracy':True,'numeric_full_acceptance':False,'client_verified':False,'old_failures_and_helpers_preserved':True,'live_core_commands_helpers_registry_modified':False};out=OUT/'freeze.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'peer_new11':True,'numeric_full':False}))
if __name__=='__main__':main()
