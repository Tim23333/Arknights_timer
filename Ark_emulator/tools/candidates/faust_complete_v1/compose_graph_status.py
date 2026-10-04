import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_faust_complete_v2_candidate'
STATUS=ROOT.parent/'unpack_work/campaign_block_status_v5_candidate';OUT=ROOT.parent/'unpack_work/campaign_faust_complete_v3_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='f9855b69eb0a0a25828448181e24436118c4c3afbfa177615921be6e37bf87b4'
    assert core(STATUS)=='635526ee6d6a0e0124ef2ab439fa4729c1caf28dc184bb62936d55b6f58e6baf'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    changes={}
    for name in ('domains/block_status.py','domains/movement.py','domains/buffs.py'):
        target=OUT/'ark_sim'/name;before=sha(target);shutil.copyfile(STATUS/'ark_sim'/name,target);changes[name]={'before':before,'sha':sha(target)}
    p=OUT/'ark_sim/rules/contracts.json';catalog=json.loads(p.read_bytes());blocking=next(c for c in catalog['contracts'] if c['id']=='blocking.eligibility')
    assert 'graph' not in blocking['implementations'];blocking['implementations'].append('graph')
    p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    report={'parent_core':core(BASE),'status_core':core(STATUS),'core':core(OUT),'catalog_sha':sha(p),'changes':changes,'full_stage_executed':False}
    target=ROOT/'validation/campaign/faust_complete_v1/graph_status_composition.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
