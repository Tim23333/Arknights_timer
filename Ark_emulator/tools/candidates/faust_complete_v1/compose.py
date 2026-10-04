import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_branch_program_v5_candidate'
STATUS=ROOT.parent/'unpack_work/campaign_block_status_v2_candidate';OUT=ROOT.parent/'unpack_work/campaign_faust_complete_v1_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='9eaa953a43ec2ab2fd5fbd8b874c7f4dcd83474df577c110fc3bee5a5ac0eb34'
    assert core(STATUS)=='c3ddfc98e173f7135567ac17e45f75801a02e92ad1d2b478c83fdc97531027ea'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    changes={}
    for name in ('domains/block_status.py','domains/providers.py','domains/movement.py'):
        target=OUT/'ark_sim'/name;old=sha(target) if target.exists() else None;shutil.copyfile(STATUS/'ark_sim'/name,target)
        changes[name]={'before_sha':old,'sha':sha(target)}
    target=ROOT/'validation/campaign/faust_complete_v1/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'branch_core':core(BASE),'status_core':core(STATUS),'core':core(OUT),'changes':changes,'full_stage_executed':False}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
