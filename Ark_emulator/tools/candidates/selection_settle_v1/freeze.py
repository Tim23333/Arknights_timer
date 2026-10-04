import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_faust_complete_v3_candidate'
RUNTIME=ROOT.parent/'unpack_work/campaign_selection_settle_v3_candidate';OUT=ROOT/'validation/campaign/selection_settle_v1/source_files'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise FileExistsError('Preserve frozen source')
    report={'parent_core':'c6cdbc1754634628913d2e3419fd9eb5ea13f3569fe4d70c14ca20c8147c9a6f',
        'core':'30e4cdfadc5a98eb59da20d89591f5f5d3d6acc8f2d9a997df5e761d759fb49d','files':{}}
    for p in sorted((RUNTIME/'ark_sim').rglob('*.py')):
        rel=p.relative_to(RUNTIME);old=BASE/rel
        if sha(p)==sha(old):continue
        target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        report['files'][str(rel)]={'parent_sha':sha(old),'sha':sha(target)}
    report['receipts']={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'validation/campaign/selection_settle_v1/special_recheck.json',
        ROOT/'validation/campaign/selection_settle_v1/contract_compat.json',ROOT/'packages/campaign/chapter05_units/special/model.selection_settle.reference.json']}
    with (OUT.parent/'freeze.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'files':len(report['files']),'sha':sha(OUT.parent/'freeze.json')}))
if __name__=='__main__':main()
