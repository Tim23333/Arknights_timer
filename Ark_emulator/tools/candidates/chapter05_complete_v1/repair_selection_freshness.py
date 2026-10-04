import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_chapter05_complete_v2_candidate'
SETTLE=ROOT.parent/'unpack_work/campaign_selection_settle_v5_candidate';OUT=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='146224f14e601ac5f2610920d644e8dc96c4478bb089917ef428e80c9ec51d70'
    assert core(SETTLE)=='6350e435fe690aa0bf03e4df7d41864c6e031d4b2c2818dbfeb1d75c5e46db26'
    if OUT.exists():raise FileExistsError('Preserve composition')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    rel=Path('ark_sim/domains/abilities.py');assert sha(BASE/'ark_sim/content/schemas.py')==sha(SETTLE/'ark_sim/content/schemas.py')
    shutil.copyfile(SETTLE/rel,OUT/rel)
    report={'parent_core':core(BASE),'settle_core':core(SETTLE),'core':core(OUT),
        'changed':{str(rel):{'old_sha':sha(BASE/rel),'sha':sha(OUT/rel)}},'full_stage_executed':False}
    target=ROOT/'validation/campaign/chapter05_complete_v1/selection_freshness_repaired.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
