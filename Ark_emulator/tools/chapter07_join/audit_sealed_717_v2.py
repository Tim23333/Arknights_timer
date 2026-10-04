"""Read completed original journal without mutating any running branch."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v7 import audit
from tools.trace_audit.stream_oracle_v5 import CONTRACTS
from tools.trace_audit.stream_oracle_v5_identity import STANDARD

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def main():
    original=Path('E:/ArkSimEvidence/campaign/07_17_3992_native_draft_v2/full_v1.original.json');r=json.loads(original.read_bytes())
    assert r['process_complete'] is True and r['forward_error'] is None and r['implementation']=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
    journal=Path(r['journal']['path']);assert journal.stat().st_size==r['journal']['bytes'] and sha(journal)==r['journal']['sha256']
    pins=ROOT/'validation/trace_audit/simple_formulas_v5/oracle_pins.json'
    package=ROOT/'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v2.life99999.strict_v2.json'
    commands=ROOT/'scenarios/campaign/chapter07/level_main_07-15/public_plan_v2/commands.json'
    paths=[original,journal,pins,package,commands,STANDARD,CONTRACTS,Path(__file__),ROOT/'tools/compare_campaign_trace.py']
    paths += [ROOT/'tools/trace_audit'/n for n in ('stream_oracle_v7.py','stream_oracle_v6.py','stream_oracle_v5.py','stream_oracle_v5_identity.py','stream_oracle_v5_math.py')]
    before={str(p):sha(p) for p in paths};assert before[str(package)]==r['package_sha256'] and before[str(commands)]==r['commands_sha256']
    witness=ROOT/'validation/trace_audit/07-17_delta_bound_v7/input_witness_pins.json'
    paths.append(witness);before[str(witness)]=sha(witness)
    out=audit(journal,json.loads(pins.read_bytes())['rules'],json.loads(witness.read_bytes()));after={str(p):sha(p) for p in paths};assert before==after and out['counts']['events']==r['journal']['events']
    out.update({'source_original_report':str(original),'source_journal_reference':r['journal'],'consumed_before':before,'consumed_after':after,
        'source_identity_stable':True,'complete_actual_sealed_trace_read':True,
        'scope':'Known frozen standard numerical formulas only. Unknown customsourceproviders/geometry/clock/capture/timing remain explicitly pending; does not register whole stage or assert all intermediate values/client equality.'})
    dest=ROOT/'validation/trace_audit/07-17.sealed_original_full.v2.json';assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'identity':out['identity_counts'],'failures':out['failures'][:5],'pending_categories':len(out['pending_fields']),'numeric_full':out['all_fields_independently_verified']}));raise SystemExit(0 if out['source_formula_consistent'] else 1)
if __name__=='__main__':main()
