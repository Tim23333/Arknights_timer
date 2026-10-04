"""Fresh joint-core gate with source/helper guards and disk-log cleanup."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT.parent/'unpack_work/campaign_c9_foundation_v4_candidate'
CORE='6e43f8827415f99f83b79ff676fae533afcfda56f326d93bef8cda488172d1f9'
LOG=Path('E:/ArkSimLogs/runs/chapter09_foundation_independent_v4')
OUT=ROOT/'validation/campaign/chapter09_foundation_independent_v4'
OLD=ROOT/'tools/chapter09_invisible_peer_final'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def guard():
 paths=list((CAND/'ark_sim').rglob('*.py'))+list((ROOT/'ark_sim').rglob('*.py'))+list(OLD.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))
 return {str(p.resolve()):sha(p) for p in sorted(paths)}
def read(path):return json.loads(path.read_text(encoding='utf8'))
def run(script,file,mode=None):
 args=[sys.executable,str(script),str(CAND),str(LOG/file)]
 if mode is not None:args.append(mode)
 subprocess.run(args,cwd=ROOT,env={**os.environ,'PYTHONHASHSEED':'0'},check=True,capture_output=True,text=True)
def main():
 LOG.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);before=guard()
 frozen={'worker.py':'bf4c1a84767c13f4f2e6406e9bf037f3609fbc9eea69be96fb545fb32cc8e675','verify.py':'2c74154d800588223003ffab4dd8d5aed3749b86f1d794c517ea575cbde84501','test_identity_boundaries.py':'ba96d28f7339bdcafa19021eff5d551d442ca44d54ead46b37c651f521b8f066'}
 assert all(sha(OLD/name)==value for name,value in frozen.items()),'frozen previous peer source changed'
 # Execute the original independent fixture against the new actual core.
 # Nothing is copied, imported, patched, or relabelled from the old receipt.
 run(OLD/'worker.py','selection.receipt.json','independent');selection=read(LOG/'selection.receipt.json');assert selection['implementation']==CORE and selection['passed'] and len(selection['checks'])==41
 run(OLD/'worker.py','cache.receipt.json','cache');cache=read(LOG/'cache.receipt.json');assert cache['implementation']==CORE and cache['passed'] and cache['all_events_equal'] and cache['legal_attribute_value_equal'] and cache['first_difference'] is None
 run(Path(__file__).with_name('joint_worker.py'),'joint.receipt.json');joint=read(LOG/'joint.receipt.json');assert joint['implementation']==CORE and joint['passed'] and len(joint['negative_checks'])==7
 after=guard();assert before==after,'source/helper changed during execution'
 receipt={'implementation':CORE,'selection':selection,'original_counter_hard_expected_CPP_all_events':cache,'fresh_element_sight_recovery_joint':joint,'strict_source_helper_guard_stable':True,'guard_before_sha':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),'guard_after_sha':hashlib.sha256(json.dumps(after,sort_keys=True).encode()).hexdigest(),'source_file_count':len(before),'helper_sources':{str(p.resolve()):sha(p) for p in list(OLD.glob('*.py'))+list(Path(__file__).parent.glob('*.py'))},'raw_sha':{p.name:sha(p) for p in LOG.iterdir() if p.is_file()},'scope':'Actual joint6e43 core; fresh selection41, repaired old query counter, own element/sight/SP/clock/owner lifecycle and cache forgery gates. Previous legacy-pair evidence is not reused as compatibility proof for new cache/trace schema.','fixture_boundary_audit':'Exploratory fixture initially expected on_end after advance to34. Read actual Session.advance documented [time,time+n) contract; final hard gate explicitly verifies due34 remains pending when clock reaches34 and end executes with eventtime34 when advancing to35. Candidate/main and frozen peer source unchanged.','passed':True}
 cleanup=subprocess.run([sys.executable,str(ROOT/'tools/cleanup_simulation_logs.py'),'--apply','--run-dir',str(LOG),'--minimum-age-minutes','0'],cwd=ROOT,capture_output=True,text=True,check=True);receipt['cleanup']=json.loads(cleanup.stdout)
 final=guard();assert final==before,'source/helper changed during cleanup';receipt['guard_after_cleanup_sha']=hashlib.sha256(json.dumps(final,sort_keys=True).encode()).hexdigest()
 (OUT/'source.guard.v4.json').write_text(json.dumps({'before':before,'after':after,'after_cleanup':final},indent=2)+'\n',encoding='utf8');receipt['source_guard_file_sha']=sha(OUT/'source.guard.v4.json')
 path=OUT/'receipt.v4.json';path.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf8');print(json.dumps({'passed':True,'selection_checks':len(selection['checks']),'joint_checks':len(joint['checks']),'cache_negative_checks':len(joint['negative_checks']),'original_counter_fixed':cache['all_events_equal'],'source_guard_stable':True,'receipt_sha':sha(path),'cleanup':receipt['cleanup']}))
if __name__=='__main__':main()
