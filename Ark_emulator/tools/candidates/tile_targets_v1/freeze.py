import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_tile_targets_v7_candidate'
DEST=ROOT/'validation/campaign/tile_targets_v1/source_files'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if DEST.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7',
        'core':'42014647b8d510c6394b98221c138a0bc27a8ccab3354d653a65fc2767fb3833','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*.py')):
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if old.exists() and sha(old)==sha(p):continue
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old) if old.exists() else None,'sha':sha(target)}
    report['receipts']={str(p.relative_to(ROOT)):sha(p) for p in [
        ROOT/'validation/campaign/tile_targets_v1/author_tests_v7.json',
        ROOT/'validation/campaign/tile_targets_v1/compat_v7.json']}
    with (DEST.parent/'freeze_v7.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'changed_files':len(report['files']),'freeze_sha':sha(DEST.parent/'freeze_v7.json')}))
if __name__=='__main__':main()
