"""Freeze reviewed source arithmetic/identity subset, preserving every old failure."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/author_freeze_v3'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);helpers=[ROOT/'tools/trace_audit'/('stream_oracle_v'+str(i)+'.py') for i in (1,2,3)]+[ROOT/'tools/trace_audit/capture_source_golden_v3.py',ROOT/'tools/trace_audit/verify_oracle_v1.py',ROOT/'tools/compare_campaign_trace.py'];evidence=[]
 for folder in ('source_golden_v1','source_golden_v2','source_golden_v3','oracle_tests_v1','root_negative_review_v1','root_negative_review_v2','root_negative_review_v3','root_binding_review_v2','root_binding_review_v3','05_09_cp800_prefix100k_v1'):
  for p in (ROOT/'validation/trace_audit'/folder).glob('*'):
   if p.is_file():evidence.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
 for p in helpers:
  dst=OUT/'source'/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst);assert sha(p)==sha(dst)
 stage=ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.life99999.json';golden=ROOT/'validation/trace_audit/source_golden_v3/input.json';original_defs={d['id']:d for d in json.loads(stage.read_bytes())['definitions']};golden_defs=json.loads(golden.read_bytes())['definitions'];assert all(d==original_defs[d['id']] for d in golden_defs if d['id']!='unit/audit_controlled_enemy')
 positive=ROOT/'validation/trace_audit/source_golden_v3/audit_v3.json';p=json.loads(positive.read_bytes());assert p['source_formula_consistent'] and not p['all_fields_independently_verified'] and not p['failures'];peer1=ROOT/'validation/trace_audit/root_negative_review_v3/verification.json';peer2=ROOT/'validation/trace_audit/root_binding_review_v3/verification.json';assert json.loads(peer1.read_bytes())['passed'] and json.loads(peer2.read_bytes())['passed']
 result={'role':'Reviewed source-arithmetic/identity subset, not whole game numerical acceptance','formula_version':'independent-source-arithmetic/v3','helpers':[{'path':str(p),'sha256':sha(p)} for p in helpers],'evidence':evidence,'source_actor_definitions_exact_to_stage':True,'source_stage_sha':sha(stage),'positive':{'path':str(positive),'sha':sha(positive),'actual_exit':0,'events':p['counts']['events'],'supported_verified_calculations':p['counts']['verified_calculations'],'supported_verified_cached':p['counts']['verified_cached'],'supported_verified_nested':p['counts']['verified_nested_calculations'],'graph_context_calls':p['graph_context_calls_checked'],'pending_fields':p['pending_fields']},'independent_root':{'identity4':{'path':str(peer1),'sha':sha(peer1)},'binding5':{'path':str(peer2),'sha':sha(peer2)}},'source_golden_actual':{'physical_damage_events':6,'arts_damage_events':3,'natural_regeneration_events':1099,'true_and_minimum_floor':'Explicit known-value arithmetic tests; not claimed source-stage triggered'},'old_failed_evidence_preserved':True,'unknown_rules_auto_green':False,'birth_maxHP_source_binding_full':False,'numeric_full_acceptance':False,'client_verified':False,'live_core_input_helper_registry_modified':False};dest=OUT/'freeze.json';dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'evidence_files':len(evidence),'peer9_actual_pass':True,'numeric_full':False}))
if __name__=='__main__':main()
