"""Preserve legitimate plain-entity public deployment when no profile exists."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m67_connectivity_snapshot_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m69_connectivity_plain_deploy_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    if core(BASE)!='138cf9a4927f20162b207d07cb34441a41aabe887e0a06630fcd36cef9a6a07b':raise ValueError('Frozen connectivity parent changed')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/deployment.py';s=p.read_text(encoding='utf8');old="context.get(ref,('deployable',)),entity=context.entity(ref),phase='record'"
    if s.count(old)!=1:raise ValueError('Optional deployment component anchor changed')
    p.write_text(s.replace(old,"context.get(ref,('deployable',),{}),entity=context.entity(ref),phase='record'",1),encoding='utf8',newline='')
    report={'core':core(OUT),'parent':core(BASE),'changed_file':'domains/deployment.py','source_sha256':sha(p),'tested':False}
    f=ROOT/'validation/campaign/m69_connectivity/composition.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
