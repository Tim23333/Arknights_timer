import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_combat_v5_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_ability_arbitration_v3_candidate'
DEST=ROOT/'validation/campaign/ability_arbitration_v1/source_files_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if DEST.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'df98feb41687d1b560d27d24bcbc7aad8bbb2f7ace48aaa67aca5816fe95e86b',
        'core':'455de2ea24f042c445483b9c05df6c1e95421db496be385e034f99ec3f20f1ae','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*.py')):
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if old.exists() and sha(old)==sha(p):continue
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old) if old.exists() else None,'sha':sha(target)}
    report['receipts']={str(p.relative_to(ROOT)):sha(p) for p in [
        ROOT/'validation/campaign/ability_arbitration_v1/author_v3_effective_inputs.json']}
    target=DEST.parent/'freeze_v3.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'changed_files':len(report['files']),'freeze_sha':sha(target)}))
if __name__=='__main__':main()
