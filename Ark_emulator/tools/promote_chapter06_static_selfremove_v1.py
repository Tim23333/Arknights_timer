"""Publish exact four-file generic candidate only after all of its own gates."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'
BACKUP=ROOT.parent/'unpack_work/primary_a705_before_chapter06_static_selfremove_v1'
OUT=ROOT/'validation/campaign/chapter06_static_selfremove_v1_primary'
OLD='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
NEW='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts}


def core(root):
    text='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',text,str(root)],cwd=root,text=True).strip()


def main():
    assert core(ROOT)==OLD and core(CANDIDATE)==NEW
    pins={'baseline':('validation/campaign/chapter06_static_selfremove_v1/baseline.identity.json','85b7d42d79a8005227259a3238535d630f2ec711f599dc483dfa1de8f1458c86'),
          'independent':('validation/campaign/chapter06_static_joint_independent/verification.json','673c6db58bf253f4e22bd10c82b6dac43e11a3730a6bd5c3eaede4abb45dc5be'),
          'independent_freeze':('validation/campaign/chapter06_static_joint_independent/freeze.json','407c55b0709514cff159645ee605aa0030364bb57aaedc312853fba5a6042469'),
          'candidate_freeze':('validation/campaign/chapter06_static_selfremove_v1/freeze.json','a6d9ce288dd347f5be6da4c0da49b0aa86c8c8a7bef806f80f1d1fb71449d4ba')}
    proofs={}
    for key,(rel,pin) in pins.items():assert sha(ROOT/rel)==pin;proofs[key]=json.loads((ROOT/rel).read_bytes())
    baseline=proofs['baseline'];assert baseline['passed'] and baseline['exit_code']==0 and baseline['identity_stable'] and baseline['implementation_sha256']==NEW
    assert baseline['source_at_start']==baseline['source_at_completion']
    for path,pin in baseline['source_at_completion'].items():assert sha(path)==pin,path
    assert sha(ROOT/'validation/campaign/chapter06_static_selfremove_v1/baseline.json')=='17939e6c91d04936ce6aa04833dfd60f295b0b99403ca75b231bc2305d84de4e'
    independent=proofs['independent'];assert independent['core']==NEW and independent['guards_equal']
    assert len(independent['cases'])==15 and all(c['outcome']=='passed' for c in independent['cases'])
    for path,pin in independent['guards_end'].items():assert sha(path)==pin,path
    suitefile=ROOT/'validation/campaign/chapter06_static_selfremove_v1/full_suite_v2/verification.json'
    suite=json.loads(suitefile.read_bytes());assert suite['core']==NEW and suite['exitcode']==0 and suite['identity_stable']
    assert suite['original_expectations_changed'] is False and not suite['collection_skips']
    assert len(suite['cases'])==1219 and all(c['outcome']=='passed' for c in suite['cases'])
    assert suite['guards_start']==suite['guards_end']
    for path,pin in suite['guards_end'].items():assert sha(path)==pin,path
    assert all(Path(p).is_relative_to(CANDIDATE/'ark_sim') for p in suite['actual_modules'].values())
    before=files(ROOT/'ark_sim');candidate=files(CANDIDATE/'ark_sim')
    changes={rel for rel,pin in candidate.items() if before.get(rel)!=pin}
    assert not set(before)-set(candidate)
    assert changes=={'content/dependencies.py','content/spatial_validation.py','domains/spatial.py','domains/tile_mechanics.py'}
    assert not BACKUP.exists() and not OUT.exists()
    shutil.copytree(ROOT/'ark_sim',BACKUP/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert files(BACKUP/'ark_sim')==before and core(BACKUP)==OLD
    for rel in changes:shutil.copyfile(CANDIDATE/'ark_sim'/rel,ROOT/'ark_sim'/rel)
    assert files(ROOT/'ark_sim')==candidate and core(ROOT)==NEW
    OUT.mkdir();report={'passed':True,'primary_before':OLD,'primary_after':NEW,'changed_files':sorted(changes),
        'backup':str(BACKUP),'before':before,'after':candidate,'proof_pins':pins,'actual_suite_sha':sha(suitefile),
        'scope':'Exact reviewed generic static tile and current-instance Buff self-removal; new content/runner/fullstage retain separate gates'}
    path=OUT/'promotion.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':sha(path)}))


if __name__=='__main__':main()
