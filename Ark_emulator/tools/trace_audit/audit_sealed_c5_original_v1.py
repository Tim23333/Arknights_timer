"""Only sealed original reports/journals; before/after exact identity, unknown stays pending."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v3 import audit
CORE='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['05-09','05-10'],required=True);a=ap.parse_args();base=Path('E:/ArkSimEvidence/campaign')/(a.stage.replace('-','_')+'_8fa4e36752e92f7d')/'public_v1.original.json';report=json.loads(base.read_bytes());assert report['process_complete'] and report['forward_error'] is None and report['implementation']==CORE;journal=Path(report['journal']['path']);assert journal.stat().st_size==report['journal']['bytes'];assert sha(journal)==report['journal']['sha256']
 prepared=json.loads((ROOT/'validation/campaign/chapter05_public_v3/prepared_commands.json').read_bytes());row=next(r for r in prepared['cases'] if r['native_id']=='level_main_'+a.stage);package=Path(row['overlay']);commands=Path(row['commands']);pins=ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json';helpers=[ROOT/'tools/trace_audit'/('stream_oracle_v'+str(i)+'.py') for i in (1,2,3)]+[ROOT/'tools/compare_campaign_trace.py',ROOT/'tools/trace_audit/audit_sealed_c5_original_v1.py'];paths=[base,journal,package,commands,pins]+helpers;before={str(p):sha(p) for p in paths};assert before[str(package)]==report['package_sha256']==row['overlay_sha'] and before[str(commands)]==report['commands_sha256']==row['commands_sha'];result=audit(journal,json.loads(pins.read_bytes())['rules']);after={str(p):sha(p) for p in paths};assert before==after and result['counts']['events']==report['journal']['events'];result['source_original_report']=str(base);result['source_journal_reference']=report['journal'];result['all_consumed_source_before']=before;result['all_consumed_source_after']=after;result['source_identity_stable']=True;result['full_sealed_trace_processed']=True;result['source_actor_ledger_does_not_imply_numeric_full_acceptance']=True;result['actual_process_CP_replay_acceptance_separate']=True;dest=ROOT/'validation/trace_audit'/(a.stage+'.sealed_original_full.v3.json');assert not dest.exists();dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'events':result['counts']['events'],'identity':result['identity_counts'],'failures':result['failures'][:8],'unknown_fields':result['pending_fields'],'numeric_full':result['all_fields_independently_verified']}));raise SystemExit(0 if result['source_formula_consistent'] else 1)
if __name__=='__main__':main()
