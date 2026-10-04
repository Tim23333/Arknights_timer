"""Freeze limited author oracle and exact golden inputs; independent gaps remain open."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/author_freeze_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);paths=[ROOT/'tools/trace_audit/stream_oracle_v1.py',ROOT/'tools/trace_audit/verify_oracle_v1.py',ROOT/'tools/compare_campaign_trace.py']+[ROOT/'tools/trace_audit'/('capture_source_golden_v'+str(n)+'.py') for n in (1,2,3)]
 evidence=[]
 for folder in ('source_golden_v1','source_golden_v2','source_golden_v3','oracle_tests_v1'):
  for p in (ROOT/'validation/trace_audit'/folder).glob('*'):
   if p.is_file():evidence.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
 for p in paths:
  dest=OUT/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert sha(dest)==sha(p)
 r={'status':'author version frozen; independent review pending','formula_version':'independent-source-arithmetic/v1','helpers':[{'path':str(p),'sha256':sha(p)} for p in paths],'evidence':evidence,'author_tests':{'receipt':str(ROOT/'validation/trace_audit/oracle_tests_v1/verification.json'),'sha':sha(ROOT/'validation/trace_audit/oracle_tests_v1/verification.json'),'actual_exit':0,'cases':12},'known_review_limits':['Standard pipeline assumes minimum ratio .05; context/parameter effective override identity not comprehensively closed.','Nested trace numeric/contract/context identity validation incomplete.','HP birth/maxHP source binding pending.','Unsupported custom rules and cache sources explicitly unverified.'],'rule_accuracy_full_acceptance':False,'source_ledger_is_not_numeric_full_pass':True,'client_verified':False,'live_core_helpers_commands_modified':False};dest=OUT/'freeze.json';dest.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'evidence_files':len(evidence),'author_full_acceptance':False}))
if __name__=='__main__':main()
