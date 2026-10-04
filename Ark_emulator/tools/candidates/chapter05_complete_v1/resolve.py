import hashlib,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_chapter05_complete_v1_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter05_complete_v2_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='fada240e5338efee3866b0689368cf07d4c59161244dde3c6e235115ff24eb94'
    if OUT.exists():raise FileExistsError('Preserve composition')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/providers.py';text=p.read_text(encoding='utf8');pattern=re.compile(r'(?m)^<<<<<<< .*?\n(.*?)^=======\n(.*?)^>>>>>>> .*?\n',re.S)
    def resolve(m):
        left,right=m.group(1),m.group(2)
        assert 'model.blocking.status' in left and 'model.projectile.cardinal_map_ray' in right
        return left+right.replace('BUILTIN_PROVIDERS = {\n','',1)
    text,count=pattern.subn(resolve,text);assert count==1;p.write_text(text,encoding='utf8',newline='')
    for p in (OUT/'ark_sim').rglob('*.py'):
        text=p.read_text(encoding='utf8');assert '<<<<<<<' not in text;compile(text,str(p),'exec')
    target=ROOT/'validation/campaign/chapter05_complete_v1/resolved_composition.json'
    report={'parent_draft_core':core(BASE),'core':core(OUT),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'resolution':'Keep actual block status and both ray providers/imports; no existing provider dropped','full_stage_executed':False}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
