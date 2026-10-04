"""Combine reviewed exit deltas with actual retained area-recipient scope."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ORIGINAL=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v15_candidate'
EXIT=ROOT.parent/'unpack_work/campaign_exit_accounting_v4_candidate'
BASE=ROOT.parent/'unpack_work/campaign_retained_area_payload_v16_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert core(BASE)=='8b9f226882502ce9b9d8029102fff5832f2ba01e5449096502908b670d889e9b'
    assert core(EXIT)=='a41a501b58fd242dd67069f9b45ec8948af914026401cae6ce580de220445e81' and not OUT.exists()
    paths=[p for folder in (BASE,EXIT,ORIGINAL) for p in (folder/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts]
    guards={str(p):sha(p) for p in paths}
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    changes={}
    for p in (EXIT/'ark_sim').rglob('*'):
        if not p.is_file() or p.suffix not in {'.py','.json'} or '__pycache__' in p.parts:continue
        rel=p.relative_to(EXIT);before=ORIGINAL/rel
        if before.exists() and p.read_bytes()==before.read_bytes():continue
        if before.exists():assert (BASE/rel).read_bytes()==before.read_bytes(),str(rel)
        target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        changes[str(rel)]={'source_sha':sha(p),'joint_sha':sha(target)}
    assert len(changes)==6 and guards=={str(p):sha(p) for p in paths}
    assert sha(OUT/'ark_sim/domains/projectiles.py')==sha(BASE/'ark_sim/domains/projectiles.py')
    target=ROOT/'validation/campaign/chapter06_complete_base_v5/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'area_parent_core':core(BASE),'exit_parent_core':core(EXIT),'core':core(OUT),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'changes_from_area':changes,'source_guards':guards,'scope':'Isolated generic base composition; source/AoE/exit combined independent/full regression pending'}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('changes_from_area','source_guards')}))


if __name__=='__main__':main()
