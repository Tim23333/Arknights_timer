import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_faust_complete_v3_candidate';DEST=ROOT/'validation/campaign/faust_complete_v1/source_files_v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if DEST.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90',
        'core':'c6cdbc1754634628913d2e3419fd9eb5ea13f3569fe4d70c14ca20c8147c9a6f','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*')):
        if not p.is_file() or p.suffix not in {'.py','.json'}:continue
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if old.exists() and sha(old)==sha(p):continue
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old) if old.exists() else None,'sha':sha(target)}
    report['receipts']={str(p.relative_to(ROOT)):sha(p) for p in [
        ROOT/'validation/campaign/faust_complete_v1/components_v3.json',
        ROOT/'packages/campaign/chapter05_boss/faust/complete.v2.reference.json',
        ROOT/'validation/campaign/faust_blockstatus_v5_independent_peer/verification.json',
        ROOT/'validation/campaign/branch_program_v5_facts_independent_peer/verification.json']}
    report['pending']='Independent combined review, full regression, ballista and chapter5 stage; not primary promotion'
    target=DEST.parent/'freeze_v3.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'files':len(report['files']),'sha':sha(target)}))
if __name__=='__main__':main()
