import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v4_candidate';DEST=ROOT/'validation/campaign/frost_complete_v1/source_files_v4'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if DEST.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7',
        'core':'db6a90c23cfeb398e20d6b0a58a51ffe10638c6c676fcee29737d91f45c20213','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*')):
        if not p.is_file() or p.suffix not in {'.py','.json'}:continue
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if old.exists() and sha(old)==sha(p):continue
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old) if old.exists() else None,'sha':sha(target)}
    report['receipts']={str(p.relative_to(ROOT)):sha(p) for p in [
        ROOT/'validation/campaign/frost_complete_v1/complete_initial.json',
        ROOT/'packages/campaign/chapter04_boss/frost_complete_v1/module.reference.json']}
    report['pending']='v4 compatibility and independent combined review; not promoted or full stage'
    target=DEST.parent/'freeze_v4.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'changed_files':len(report['files']),'freeze_sha':sha(target)}))
if __name__=='__main__':main()
