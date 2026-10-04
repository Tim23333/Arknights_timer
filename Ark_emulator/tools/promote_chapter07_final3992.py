"""Promote only the final candidate's own frozen tested bytes."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate'
OLD='4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346'
NEW='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
CHANGES={'adapters/api.py','content/capabilities.py','content/dependencies.py',
         'content/schemas.py','domains/effects.py','domains/movement.py'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*')
    if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts}


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def bound(path,pin):
    assert sha(path)==pin,str(path)
    return json.loads(Path(path).read_bytes())


def main():
    assert core(ROOT)==OLD and core(CAND)==NEW
    freeze=bound(ROOT/'validation/campaign/area_projection_v2/freeze.json',
                 '7616efc00d63bb48e3c0091f0e9b12eff222975b53359237484ea16b6468b88b')
    assert freeze['core']==NEW
    for p,h in freeze['files'].items():assert sha(p)==h,p
    peer=bound(ROOT/'validation/campaign/chapter07_final3992_independent_gate/freeze.json',
               '1fc165cc4185a4d2a81d73caccfcf00aead1aca605d963189c5c4a2db2cd814b')
    assert peer['passed'] is True and peer['core']==NEW
    assert peer['actual_executed_cases']==37 and peer['unique_cases']==36
    for p,h in peer['files'].items():assert sha(p)==h,p
    for item in peer['reports']:
        report=bound(item['path'],item['sha'])
        assert report['core']==NEW and report['exit']==0 and report['guards_equal'] is True
        assert len(report['cases'])==item['actual_cases'] and all(c['outcome']=='passed' for c in report['cases'])
        for p,h in report['guards_end'].items():assert sha(p)==h,p
    baseline=bound(ROOT/'validation/campaign/area_projection_v2/baseline.identity.json',
                   '2d5fcd498a3c30620f83c685417534126abf5ae0f6bac8735d0b5208c41dfe37')
    assert baseline['passed'] is True and baseline['exit_code']==0 and baseline['identity_stable'] is True
    assert baseline['implementation_sha256']==NEW and baseline['source_at_start']==baseline['source_at_completion']
    for p,h in baseline['source_at_completion'].items():assert sha(p)==h,p
    assert sha(ROOT/'validation/campaign/area_projection_v2/baseline.json')=='ed44173792b12bcecaa7bb668c863624013e8eb9d456ad46e3811c5edcb97f4a'
    author=bound(ROOT/'validation/campaign/area_projection_v2/author_verification.json',
                 '948093af64ded7c60c2640f6d0a7ccbe0df2de8a4050c84b9e277b2e0e6e2c1b')
    assert author['actual_exit']==0 and author['core']==NEW and author['guards_equal'] is True
    assert len(author['cases'])==45 and all(c['outcome']=='passed' for c in author['cases'])
    for p,h in author['guards_end'].items():assert sha(p)==h,p
    suitefile=ROOT/'validation/campaign/area_projection_v2/full_suite_v1/verification.json'
    suite=json.loads(suitefile.read_bytes())
    assert suite['passed'] is True and suite['exitcode']==0 and suite['identity_stable'] is True and suite['core']==NEW
    assert not suite['collection_skips'] and suite['original_expectations_changed'] is False
    assert len(suite['cases'])==1219 and all(c['outcome']=='passed' for c in suite['cases'])
    assert suite['guards_start']==suite['guards_end']
    for p,h in suite['guards_end'].items():assert sha(p)==h,p
    assert all(Path(p).is_relative_to(CAND/'ark_sim') for p in suite['actual_modules'].values())
    before,after=files(ROOT/'ark_sim'),files(CAND/'ark_sim')
    assert set(before)==set(after) and {p for p,h in after.items() if before[p]!=h}==CHANGES
    backup=ROOT.parent/'unpack_work/primary_4f16_before_chapter07_final3992'
    out=ROOT/'validation/campaign/chapter07_final3992_primary'
    assert not backup.exists() and not out.exists()
    shutil.copytree(ROOT/'ark_sim',backup/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert files(backup/'ark_sim')==before and core(backup)==OLD
    for p in sorted(CHANGES):shutil.copyfile(CAND/'ark_sim'/p,ROOT/'ark_sim'/p)
    assert files(ROOT/'ark_sim')==after and core(ROOT)==NEW
    out.mkdir();p=out/'promotion.json';p.write_text(json.dumps({'passed':True,
        'primary_before':OLD,'primary_after':NEW,'changed_files':sorted(CHANGES),'backup':str(backup),
        'before':before,'after':after,'own_suite_sha':sha(suitefile),
        'peer_freeze_sha':sha(ROOT/'validation/campaign/chapter07_final3992_independent_gate/freeze.json'),
        'baseline_guard_sha':sha(ROOT/'validation/campaign/area_projection_v2/baseline.identity.json'),
        'scope':'Exact own-gated finite separate scenario cards/custom area live projection/public motion typed-state synchronization. Parent generic waiting/aura/wave/cache capabilities retained. Oldreports stay oldidentity; no wholeC7/client accuracy claim.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'core':NEW,'sha':sha(p)}))


if __name__=='__main__':main()
