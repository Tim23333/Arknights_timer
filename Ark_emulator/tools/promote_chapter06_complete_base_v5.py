"""Publish exact reviewed Buff base while newer payload/exit candidates stay isolated."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
BACKUP=ROOT.parent/'unpack_work/primary_buff_v9_before_chapter06_complete_base_v5'
OUT=ROOT/'validation/campaign/chapter06_complete_base_v5_primary'
OLD='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4'
NEW='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
PINS={
 'suite':('validation/campaign/chapter06_complete_base_v5/full_base_v5.json','529500eb6ead53ca68cac01f8254d0dc8d67a6902ee9a46b5f7e48ace09126c2'),
 'baseline':('validation/campaign/chapter06_complete_base_v5/baseline_base_v5_guard.json','08a1c6f6e772e238d4818321748eade2c5185b514b1e76ddb717503507b2a4e8'),
 'independent':('validation/campaign/chapter06_base_joint_independent_peer/verification.json','7025c58257c72da376720b2353c4e41ffef6464aa9e680b27b836ea13fdb7394'),
 'independent_freeze':('validation/campaign/chapter06_base_joint_independent_peer/freeze.json','89c23cb8f9843f485ea36644d80c25add283f3909765c25fec683480fa3ce28b'),
 'source_probe':('validation/campaign/chapter06_complete_base_v5/source_probes/verification.json','e5357d5fd57d5432439c1f553b25ab064ab3185bd771214ebef9ff610c8a98b6'),
 'source_slug':('validation/campaign/chapter06_complete_base_v5/slug_probes/verification.json','c6ee666192e1edb6a6ff7096e7f1b663b07e77200763be8f33bfd045f4892ac7')}



def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def files(root):return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
                       if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts}


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert core(ROOT)==OLD and core(CANDIDATE)==NEW
    proofs={}
    for name,(rel,pin) in PINS.items():
        assert sha(ROOT/rel)==pin,name;proofs[name]=json.loads((ROOT/rel).read_bytes())
    suite=proofs['suite'];assert suite['core']==NEW and suite['exitcode']==0
    assert len(suite['cases'])==1219 and all(c['outcome']=='passed' for c in suite['cases'])
    assert suite['guards_start']==suite['guards_end']
    for path,pin in suite['guards_end'].items():assert sha(Path(path))==pin,path
    assert all(Path(path).is_relative_to(CANDIDATE/'ark_sim') for path in suite['actual_modules'].values())
    baseline=proofs['baseline'];assert baseline['core']==NEW and baseline['exitcode']==0
    for path,pin in baseline['guards'].items():assert sha(Path(path))==pin,path
    bfile=ROOT/'validation/campaign/chapter06_complete_base_v5/baseline_base_v5.json';assert sha(bfile)==baseline['baseline_sha']
    b=json.loads(bfile.read_bytes());assert b['passed'] and b['level_00_01']['final_state']['kills']==11
    assert all(v['replay_equal'] and v['damage']==v['expected'] for v in b['custom_rulesets'].values())
    independent=proofs['independent'];assert independent['core']==NEW and independent['guards_equal']
    assert independent['guards_start']==independent['guards_end'] and len(independent['cases'])==44 and all(c['outcome']=='passed' for c in independent['cases'])
    frozen=proofs['independent_freeze'];assert frozen['core']==NEW and frozen['all_passed'] and (frozen['cases']==44 or len(frozen['cases'])==44)
    for rel,pin in frozen['artifacts'].items():assert sha(ROOT/rel)==pin,rel
    probe=proofs['source_probe'];assert probe['passed'] and probe['core']==NEW and all(row['passed'] for row in probe['results'])
    slug=proofs['source_slug'];assert slug['passed'] and slug['core']==NEW and all(c['passed'] for c in slug['cases'])
    before,candidate=files(ROOT/'ark_sim'),files(CANDIDATE/'ark_sim')
    assert not set(before)-set(candidate)
    changed={name for name in candidate if before.get(name)!=candidate[name]}
    expected={'content/capabilities.py','content/compiler.py','content/schemas.py','domains/buff_application.py','domains/effects.py','domains/exit_accounting.py','domains/lifecycle.py','domains/projectiles.py','rules/contracts.json'}
    assert changed==expected
    assert not BACKUP.exists() and not OUT.exists()
    shutil.copytree(ROOT/'ark_sim',BACKUP/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert files(BACKUP/'ark_sim')==before and core(BACKUP)==OLD
    for rel in changed:
        dest=ROOT/'ark_sim'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CANDIDATE/'ark_sim'/rel,dest)
    assert files(ROOT/'ark_sim')==candidate and core(ROOT)==NEW
    OUT.mkdir(parents=True)
    report={'passed':True,'primary_before':OLD,'primary_after':NEW,'backup':str(BACKUP),'changed_files':sorted(changed),
            'files_before':before,'files_after':candidate,'proof_pins':PINS,'scope':'Exact reviewed generic base; newer payload/exit and source unit contents have separate evidence gates'}
    target=OUT/'promotion.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'passed':True,'core':NEW,'files':len(candidate),'changes':len(changed),'sha':sha(target)}))


if __name__=='__main__':main()
