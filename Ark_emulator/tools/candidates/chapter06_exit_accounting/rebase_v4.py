"""Three-way exit integration preserves the real revive incarnation counter."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v14_candidate'
EXIT=ROOT.parent/'unpack_work/campaign_exit_accounting_v3_candidate'
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v15_candidate'
OUT=ROOT.parent/'unpack_work/campaign_exit_accounting_v4_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert core(BASE)=='b3d51a11e499b693e22cf7750555629423b009413ed2d84a6d3ffb3dccace2c6'
    assert core(EXIT)=='efad001ce0b34274301b417821e0d24df8abb14c956e4c7ef099ea74a1d95322' and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    deltas={}
    for p in (EXIT/'ark_sim').rglob('*'):
        if not p.is_file() or p.suffix not in {'.py','.json'} or '__pycache__' in p.parts:continue
        rel=p.relative_to(EXIT);original=OLD/rel
        if original.exists() and p.read_bytes()==original.read_bytes():continue
        target=OUT/rel
        if not original.exists() or (BASE/rel).read_bytes()==original.read_bytes():
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        else:
            merged=subprocess.run(['git','merge-file','-p',str(BASE/rel),str(original),str(p)],capture_output=True)
            assert merged.returncode==0,str(rel);target.write_bytes(merged.stdout)
        deltas[str(rel)]={'exit_sha':sha(p),'joint_sha':sha(target)}
    assert len(deltas)==6
    assert 'lifecycle_generation' in (OUT/'ark_sim/domains/lifecycle.py').read_text(encoding='utf8')
    assert sha(OUT/'ark_sim/domains/buff_application.py')==sha(BASE/'ark_sim/domains/buff_application.py')
    target=ROOT/'validation/campaign/exit_accounting_v4/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    value={'parent_core':core(BASE),'core':core(OUT),'exit_source_core':core(EXIT),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'deltas':deltas,'scope':'Source-exit accounting combined with source/target revive identity; independent proof pending'}
    with target.open('x',encoding='utf8') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in value.items() if k!='deltas'}))


if __name__=='__main__':main()
