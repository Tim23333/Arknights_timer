import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_tile_targets_v8_candidate';DEST=ROOT/'validation/campaign/tile_targets_v1/source_files_v8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if DEST.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7',
        'core':'99a7aeff1cfe91806b1c0cf283e138fce75a5150d821535976072e4dd3080074','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*.py')):
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if old.exists() and sha(old)==sha(p):continue
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old) if old.exists() else None,'sha':sha(target)}
    report['receipts']={str(p.relative_to(ROOT)):sha(p) for p in [
        ROOT/'validation/campaign/tile_targets_v1/author_tests_v8.json',
        ROOT/'validation/campaign/tile_targets_v1/independent_cases_recheck_v8.json',
        ROOT/'validation/campaign/tile_targets_v7_independent_peer/verification.json']}
    target=DEST.parent/'freeze_v8.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'changed_files':len(report['files']),'freeze_sha':sha(target)}))
if __name__=='__main__':main()
