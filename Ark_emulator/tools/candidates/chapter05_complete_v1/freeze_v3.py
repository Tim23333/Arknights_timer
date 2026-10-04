import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/campaign/chapter05_complete_v1/source_files_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90',
        'core':'8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*')):
        if not p.is_file() or p.suffix not in {'.py','.json'}:continue
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if old.exists() and sha(p)==sha(old):continue
        target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old) if old.exists() else None,'sha':sha(target)}
    paths=['validation/campaign/chapter05_complete_v1/baseline_v3_guard.json',
        'validation/campaign/chapter05_complete_v1/source_chain_disk_v3.json',
        'validation/campaign/chapter05_complete_v1/prefix_v3/verification.json',
        'validation/campaign/c5_joint_source_independent_v2/freeze.json',
        'validation/campaign/selection_settle_v5_fresh_independent_peer/verification.json',
        'validation/campaign/chapter05_ballista_v1/freeze.json']
    report['receipts']={p:sha(ROOT/p) for p in paths};report['pending']='Full suite ongoing; complete chapter5 stages pending; no primary promotion'
    target=OUT.parent/'freeze_v3.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'files':len(report['files']),'sha':sha(target)}))
if __name__=='__main__':main()
