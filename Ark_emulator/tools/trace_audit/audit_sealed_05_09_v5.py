"""Source-only full sealed audit with three reviewed added formulas and exact guards."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v5 import audit
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 original=Path('E:/ArkSimEvidence/campaign/05_09_8fa4e36752e92f7d/public_v1.original.json');r=json.loads(original.read_bytes());assert r['process_complete'] and r['forward_error'] is None;journal=Path(r['journal']['path']);assert journal.stat().st_size==r['journal']['bytes'] and sha(journal)==r['journal']['sha256'];pins=ROOT/'validation/trace_audit/simple_formulas_v5/oracle_pins.json';package=ROOT/'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.life99999.json';commands=ROOT/'scenarios/campaign/chapter05/level_main_05-09/combined_v3/public_fixed12.compact_v1.commands.json';helpers=[ROOT/'tools/trace_audit'/name for name in ('stream_oracle_v5.py','stream_oracle_v5_math.py','stream_oracle_v5_identity.py')]+[ROOT/'tools/compare_campaign_trace.py',Path(__file__)];paths=[original,journal,package,commands,pins]+helpers;before={str(p):sha(p) for p in paths};assert before[str(package)]==r['package_sha256'] and before[str(commands)]==r['commands_sha256'];out=audit(journal,json.loads(pins.read_bytes())['rules']);after={str(p):sha(p) for p in paths};assert before==after and out['counts']['events']==r['journal']['events'];out.update({'source_original_report':str(original),'source_journal_reference':r['journal'],'consumed_before':before,'consumed_after':after,'source_identity_stable':True,'complete_actual_sealed_trace_read':True,'three_added_formula_scope':'time.quantize, ability.windup, deploy.refund only. Actor HP birth/effective capacity and custom formulas remain unverified.'});dest=ROOT/'validation/trace_audit/05-09.sealed_original_full.v5.json';assert not dest.exists();dest.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'identity':out['identity_counts'],'failures':out['failures'][:5],'pending_categories':len(out['pending_fields']),'numeric_full':out['all_fields_independently_verified']}));raise SystemExit(0 if out['source_formula_consistent'] else 1)
if __name__=='__main__':main()
