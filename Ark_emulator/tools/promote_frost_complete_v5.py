"""Publish exactly reviewed V2 bytes, preserving primary M68 and old receipts."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CANDIDATE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
BACKUP=ROOT.parent/'unpack_work/primary_m68_before_frost_v5_promotion';OUT=ROOT/'validation/campaign/frost_v5_primary'
OLD='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
NEW='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root):return {str(p.relative_to(root)).replace('\\','/'):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json'}}
def identity(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()
def main():
    assert identity(ROOT)==OLD and identity(CANDIDATE)==NEW
    pins={'full_suite':('validation/campaign/frost_complete_v1/full_v5_correct_fixture.json','ca842366aff1c26daec404dd3fb330645921f948c383cb76758e96f5012ee316'),
        'baseline':('validation/campaign/frost_complete_v1/baseline_v5_guard.json','3ca96e3095ad247646edd2c318c87e19ff33ebb2774f08cace85ba7bf5fa6ee0'),
        'independent_frost':('validation/campaign/frost_complete_v5_independent_peer/verification.json','097e63f70d3c3df4877f55d5f2ee8d007994f0fec4da62022ce28282f9a57ca5'),
        'independent_tiles':('validation/campaign/tile_targets_v10_independent_recheck/verification.json','f81d441f930554cc55a314b6b3ac867903b80fb820949737d0118d22d20c8d16')}
    for name,(path,pin) in pins.items():assert sha(ROOT/path)==pin,(name,path)
    suite=json.loads((ROOT/pins['full_suite'][0]).read_bytes());assert suite['exitcode']==0 and suite['core']==NEW and all(c['outcome']=='passed' for c in suite['cases'])
    baseline=json.loads((ROOT/pins['baseline'][0]).read_bytes());assert baseline['exitcode']==0 and baseline['core']==NEW
    for name in ('independent_frost','independent_tiles'):
        proof=json.loads((ROOT/pins[name][0]).read_bytes());assert proof['core_start']==proof['core_end']==NEW and proof['guards_equal'] and all(c['outcome']=='passed' for c in proof['cases'])
    before,candidate=files(ROOT/'ark_sim'),files(CANDIDATE/'ark_sim')
    assert not set(before)-set(candidate),'Unexpected primary files need review'
    if BACKUP.exists():raise FileExistsError('Preserve previous backup')
    shutil.copytree(ROOT/'ark_sim',BACKUP/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert files(BACKUP/'ark_sim')==before and identity(BACKUP)==OLD
    for name in candidate:
        dest=ROOT/'ark_sim'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CANDIDATE/'ark_sim'/name,dest)
    assert files(ROOT/'ark_sim')==candidate and identity(ROOT)==identity(CANDIDATE)==NEW
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'promotion.json'
    with target.open('x',encoding='utf8') as f:json.dump({'passed':True,'primary_before':OLD,'primary_after':NEW,
        'backup':str(BACKUP),'files_before':before,'files_after':candidate,'proof_pins':pins,
        'scope':'Byte-identical primary publication only; old proofs retain old input/core identities'},f,indent=2)
    print(json.dumps({'passed':True,'core':NEW,'files':len(candidate),'receipt_sha':sha(target)}))
if __name__=='__main__':main()
