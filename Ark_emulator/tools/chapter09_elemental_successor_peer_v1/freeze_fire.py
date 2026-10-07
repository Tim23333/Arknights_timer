"""Pin completed native source business proof, not whole-stage acceptance."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter09_elemental_successor_peer_v1';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    path=OUT/'native.fire.actual.v2.json';report=json.loads(path.read_bytes());assert report['actual_exit']==0 and report['source_equal'] and len(report['results'])==3 and all(r['passed'] for r in report['results']) and all(sha(f)==h for f,h in report['source_after'].items())
    receipts=[]
    for v in [1,2]:
        f=Path('E:/ArkSimLogs/receipts')/('chapter09_native_fire_fixed_actor_peer_v'+str(v))/'completion.json';r=json.loads(f.read_bytes());assert r['cleanup_exit']==0 and r['raw_logs_removed_after_validation'];receipts.append({'path':str(f),'sha256':sha(f),'cleanup':r['cleanup_result']})
    receipt={'schema':'ark-sim/native-fixed-actor-elemental-business-freeze/v1','core':report['core'],'actual_report':{'path':str(path),'sha256':sha(path)},'current_source_guards':report['source_after'],'business_groups_passed':3,'facts':report['facts'],'helpers':{str(f):sha(f) for f in [Path(__file__),Path(__file__).with_name('test_native_fire.py')]},'source_isolation':'Only explicit auto conditions setFalse, all source bodies/HP/resources/owned abilities preserved','original_failed_report':{'path':str(OUT/'native.fire.actual.v1.json'),'sha256':sha(OUT/'native.fire.actual.v1.json')},'cleanup':receipts,'deleted_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts),'remaining_raw':0,'errors':0,'scope':'918 nativeFlame to realFixedLiskam actualHP/FIRE/SP/cancel/radius + fullCPP/head. Source919 has no Flamer; no invented stageFIRE. OriginalM26SP doubledeclaration preserved, client attribution unverified. No whole or genericphase/resource successor claim.','whole_stage_approved':False,'client_verified':False}
    file=OUT/'native.fire.freeze.v1.json';assert not file.exists();file.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps({'freeze_sha256':sha(file),'deleted_bytes':receipt['deleted_bytes'],'raw_remaining':0}))
if __name__=='__main__':main()
