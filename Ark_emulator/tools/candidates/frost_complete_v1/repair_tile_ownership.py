import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v4_candidate'
TILE=ROOT.parent/'unpack_work/campaign_tile_targets_v10_candidate';OUT=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='db6a90c23cfeb398e20d6b0a58a51ffe10638c6c676fcee29737d91f45c20213'
    assert core(TILE)=='2eeca1dc0a9a02f2ba42aed2285d0ea89062029de8e2c58506c30e41472462cb'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    rel=Path('ark_sim/domains/tile_targets.py');shutil.copyfile(TILE/rel,OUT/rel)
    report={'parent_core':core(BASE),'tile_core':core(TILE),'core':core(OUT),
        'changed':{str(rel):{'old_sha':sha(BASE/rel),'sha':sha(OUT/rel)}},'full_stage_executed':False}
    target=ROOT/'validation/campaign/frost_complete_v1/tile_ownership_repaired.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
