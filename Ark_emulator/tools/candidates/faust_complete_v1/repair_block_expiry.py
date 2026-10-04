import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_faust_complete_v1_candidate'
STATUS=ROOT.parent/'unpack_work/campaign_block_status_v3_candidate';OUT=ROOT.parent/'unpack_work/campaign_faust_complete_v2_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='1b7f95a9a5436e95a052f361f4fc388805fa5ce519913192d87e975616a2aa1b'
    assert core(STATUS)=='f00b098ccf3ac05144d440dd18b554af87479e8ef0178eff4f2301e061f6a5d6'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=Path('ark_sim/domains/buffs.py');shutil.copyfile(STATUS/p,OUT/p)
    report={'parent_core':core(BASE),'status_core':core(STATUS),'core':core(OUT),'changed':str(p),'full_stage_executed':False}
    target=ROOT/'validation/campaign/faust_complete_v1/block_expiry_repair.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
