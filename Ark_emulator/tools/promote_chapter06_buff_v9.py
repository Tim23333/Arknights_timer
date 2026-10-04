"""Publish exact reviewed Buff base while newer payload/exit candidates stay isolated."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate'
BACKUP=ROOT.parent/'unpack_work/primary_8fa_before_chapter06_buff_v9_promotion'
OUT=ROOT/'validation/campaign/chapter06_buff_v9_primary'
OLD='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
NEW='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4'
PINS={
 'suite':('validation/campaign/chapter06_buff_join_v9/full_v9_actual.json','e7eed8828a76d5671b41cb87ba4a45a7f5352032aee1c7462b3b696bdee8c26e'),
 'baseline':('validation/campaign/chapter06_buff_join_v9/baseline_v9_guard.json','a5e1f596b527259c36a3a21cfc4dcc68ad09feff518150e6adf3a9bb56507fb6'),
 'independent':('validation/campaign/chapter06_buff_joint_peer_v9_final/verification.json','e11f89ca3c33dcff0d2f70c1a5e6277c2b48e3585748cdd5a5bf6b2806a3bdee'),
 'independent_freeze':('validation/campaign/chapter06_buff_joint_peer_v9_final/freeze.json','ed6f921a430697b6b82e2fee70031f73324aedb97f1601f2af514d4dffafe68f'),
 'source_probe':('validation/campaign/root_cold_joint_probe_v9/verification.json','edf4a9a41666a381ba9d1ffaf6cfc274d3c50f756b71d952dca7ca3412137ca7')}


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
    bfile=ROOT/'validation/campaign/chapter06_buff_join_v9/baseline_v9.json';assert sha(bfile)==baseline['baseline_sha']
    b=json.loads(bfile.read_bytes());assert b['passed'] and b['level_00_01']['final_state']['kills']==11
    assert all(v['replay_equal'] and v['damage']==v['expected'] for v in b['custom_rulesets'].values())
    independent=proofs['independent'];assert independent['core']==NEW and independent['guards_equal']
    assert independent['guards_before']==independent['guards_after'] and len(independent['cases'])==37 and all(c['outcome']=='passed' for c in independent['cases'])
    frozen=proofs['independent_freeze'];assert frozen['core']==NEW and frozen['passes']==37 and frozen['failures']==0
    for rel,pin in frozen['artifacts'].items():assert sha(ROOT/rel)==pin,rel
    probe=proofs['source_probe'];assert probe['passed'] and probe['core']==NEW and probe['checkpoint_equal'] and probe['head_replay_equal']
    before,candidate=files(ROOT/'ark_sim'),files(CANDIDATE/'ark_sim')
    assert not set(before)-set(candidate)
    changed={name for name in candidate if before.get(name)!=candidate[name]}
    expected={'content/compiler.py','content/schemas.py','domains/buffs.py','domains/buff_application.py','domains/effects.py','rules/contracts.json'}
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
