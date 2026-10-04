"""Promote ownfullytested generic restart+readonlyclock foundation only."""
import sys,json,hashlib,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CAND=ROOT.parent/'unpack_work/campaign_behavior_restart_clock_v2_candidate'
OLD='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
NEW='9ad987656683e771ea2c280e10316397efeaa5e5a7474d362c38aa18db67f54e'
CHANGES={'content/capabilities.py','content/compiler.py','content/dependencies.py','content/schemas.py','domains/behavior.py','domains/behavior_restart.py','domains/effects.py','domains/movement.py'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def files(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts}
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def bound(p,h):assert sha(p)==h,str(p);return json.loads(Path(p).read_bytes())
def pins(data):
    for n,h in data.items():assert sha(n)==h,n
def main():
    assert core(ROOT)==OLD and core(CAND)==NEW
    suitefile=ROOT/'validation/campaign/chapter08_restart_clock_v2/full_suite/verification.json';suite=bound(suitefile,'c30befd6240a3190496afc02e8619702010b817ca1cd5dabe18a3ba5acbc8ca7')
    assert suite['passed'] is True and suite['exitcode']==0 and suite['core']==NEW and suite['identity_stable'] is True
    assert len(suite['cases'])==1219 and all(x['outcome']=='passed' for x in suite['cases']) and not suite['collection_skips']
    assert suite['guards_start']==suite['guards_end'];pins(suite['guards_end']);assert all(Path(x).is_relative_to(CAND/'ark_sim') for x in suite['actual_modules'].values())
    basefile=ROOT/'validation/campaign/chapter08_restart_clock_v2/baseline/verification.identity.json';base=bound(basefile,'ee81d82ea5c6455ce45e14dfdee415bf3fdd139df6d4b0e89dd375d0c51c0b0f')
    assert base['passed'] is True and base['exit_code']==0 and base['implementation_sha256']==NEW and base['source_at_start']==base['source_at_completion'];pins(base['source_at_completion'])
    assert sha(ROOT/'validation/campaign/chapter08_restart_clock_v2/baseline/verification.json')==base['baseline_sha256']
    peerfile=ROOT/'validation/campaign/chapter08_restart_independent_v6/freeze.json';peer=bound(peerfile,'739d205855364e506b0bc36d8c8f6948aaf571ccbc58a25c4374c9b86a4b3931')
    assert peer['passed'] is True and peer['core']==NEW and peer['cases']==peer['unique_cases']==17 and peer['guards_start']==peer['guards_end'] and peer['guards_equal'] is True;pins(peer['guards_end']);pins(peer['artifact_pins'])
    verification=bound(ROOT/'validation/campaign/chapter08_restart_independent_v6/verification.json','a8c0e4147e565d3261d6fa40b9f44cb14f101a49d749370762db64b11f48f967')
    assert verification['exit']==0 and verification['core']==NEW and verification['guards_equal'] is True and len(verification['cases'])==17 and all(x['outcome']=='passed' for x in verification['cases'])
    before,after=files(ROOT/'ark_sim'),files(CAND/'ark_sim');assert set(before)<=set(after) and set(after)-set(before)=={'domains/behavior_restart.py'}
    assert {n for n,h in after.items() if before.get(n)!=h}==CHANGES
    backup=ROOT.parent/'unpack_work/primary_3992_before_chapter08_restart_clock_v2';out=ROOT/'validation/campaign/chapter08_restart_clock_primary';assert not backup.exists() and not out.exists()
    shutil.copytree(ROOT/'ark_sim',backup/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));assert files(backup/'ark_sim')==before and core(backup)==OLD
    for name in sorted(CHANGES):shutil.copyfile(CAND/'ark_sim'/name,ROOT/'ark_sim'/name)
    assert files(ROOT/'ark_sim')==after and core(ROOT)==NEW
    out.mkdir();p=out/'promotion.json';p.write_text(json.dumps({'passed':True,'primary_before':OLD,'primary_after':NEW,'changes':sorted(CHANGES),'before':before,'after':after,'backup':str(backup),'own_suite_sha':sha(suitefile),'baseline_guard_sha':sha(basefile),'independent_freeze_sha':sha(peerfile),'scope':'Exactselfgated genericfinite restart and pure targettime/seconds/quantum. Dynamic lifetime/rebirthself candidates remain isolated; no completeC8/client/whole approval.'},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':NEW,'sha':sha(p),'passed':True}))
if __name__=='__main__':main()
