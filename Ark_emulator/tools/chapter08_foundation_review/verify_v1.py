import sys,json,hashlib,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate';PARENT=ROOT.parent/'unpack_work/campaign_wave_track_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
import pytest
from tools.chapter08_foundation_review.compare_pair_v1 import compare,PAIR
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=[]
 for runtime in (CAND,PARENT):paths+=list((runtime/'ark_sim').rglob('*.py'))+list((runtime/'ark_sim').rglob('*.json'))
 paths+=list(Path(__file__).parent.glob('*.py'))+[ROOT/'tools/campaign_ordered_checkpoint.py',PAIR/'parent/capture.json',PAIR/'candidate/capture.json',PAIR/'verification.json'];before={str(p):sha(p) for p in paths};assert implementation_digest()=='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae';a=json.loads((PAIR/'parent/capture.json').read_bytes());b=json.loads((PAIR/'candidate/capture.json').read_bytes());differences=compare(a,b);cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name(n)) for n in ['test_kernel_v1.py','test_views_v1.py','test_wave_v1.py','test_comparator_v1.py']]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after;imports={k:str(Path(m.__file__).resolve()) for k,m in sys.modules.items() if k.startswith('ark_sim') and getattr(m,'__file__',None)};assert all(Path(p).is_relative_to(CAND/'ark_sim') for p in imports.values());out=ROOT/'validation/campaign/chapter08_foundation_independent_final_v1';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'core':implementation_digest(),'cases':cases,'elapsed':time.monotonic()-start,'paired_cases':3,'pair_only_actual_runtime_FP_differences':differences,'all_value_context_cache_dictionary_order_checked':True,'source_before':before,'source_after':after,'actual_imports':imports,'scope':'Fresh isolated stores/adoptonce/aliases/tombstone versions/nestedJSON/unicode/-0.0/keyorder/subtreeimmutability/string-subclassnoUserdeepcopy/sessionRLockcrossThread blocking/nestedtransactionallstore/RNG/events/tasks allocatorrollback/publicinvalidJSON andtypedFP shape. Differentwavehealth1733/restore.6/wait.7/transfer20/birth3/16/27 and CPP13/head, sourceintentFalse->True/no downgrade/foreignreject plusactualqueuedlatefault rolledallwrites/RNG/events/newtasks butcommittedtransferretained. Three parent4bf/candidate82db paired fullcheckpoint/snapshot/replay/traces/memocaches/views/keyorder; comparator negativesreject context/value/cache/order/unknownFPpath. No authorfixture imports. No performance claim or whole-stage/client proof.'},indent=2),encoding='utf8');print(json.dumps({'sha':sha(f),'actual_exit':code,'cases':len(cases)}));raise SystemExit(code)
if __name__=='__main__':main()
