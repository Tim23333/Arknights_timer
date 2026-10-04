"""Promote one frozen protocol extension after own full/base and peer gates."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT.parent/'unpack_work/campaign_no_source_types_v1_candidate'
OLD='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
NEW='5c729384f50e078bd3d3ac9d211360b17bc486588770914efe92ef5b4e983826'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core(root):
    return subprocess.check_output([sys.executable,'-c',
       'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
       str(root)],cwd=root,text=True).strip()


def inventory(root):
    return {str(path.relative_to(root)).replace('\\','/'):sha(path) for path in root.rglob('*')
            if path.is_file() and path.suffix in ('.py','.json')}


def pins(values):
    for name,value in values.items():assert sha(name)==value,name


def bound(path,value):
    assert sha(path)==value,str(path)
    return json.loads(Path(path).read_bytes())


def main():
    assert core(ROOT)==OLD and core(CAND)==NEW
    suite_path=ROOT/'validation/campaign/chapter09_no_source_types_v1/full_suite/verification.json'
    suite=bound(suite_path,'633af8b89739cc286db2085d2e25c29435b131a19fe1598dc02c81ab8def9cc5')
    assert suite['passed'] and suite['identity_stable'] and suite['exitcode']==0 and suite['core']==NEW
    assert len(suite['cases'])==1219 and all(row['outcome']=='passed' for row in suite['cases'])
    assert not suite['collection_skips'] and suite['all_other_1218_expectations_unchanged']
    assert suite['guards_start']==suite['guards_end'];pins(suite['guards_end'])
    assert all(Path(path).is_relative_to(CAND/'ark_sim') for path in suite['actual_modules'].values())
    baseline_path=ROOT/'validation/campaign/chapter09_no_source_types_v1/baseline/verification.identity.json'
    baseline=bound(baseline_path,'5dbc9ca8a712d36d542e791bbe855c41030e8f81dea2e91c32f6f7368afb2d70')
    assert baseline['passed'] and baseline['identity_stable'] and baseline['exit_code']==0
    assert baseline['implementation_sha256']==NEW and baseline['source_at_start']==baseline['source_at_completion']
    pins(baseline['source_at_completion'])
    peer_path=ROOT/'validation/campaign/chapter08_no_source_types_independent_final/freeze.json'
    peer=bound(peer_path,'03ef7bc44ca9273470b500266632b3d1eaa36b16ed2302e91b2ea2c16ae93b48')
    assert peer['core']==NEW and peer['actual_exit']==0 and peer['unique_passed']==18 and peer['guards_stable']
    pins(peer['pins'])
    before,after=inventory(ROOT/'ark_sim'),inventory(CAND/'ark_sim')
    assert before.keys()==after.keys()
    changes=[key for key in before if before[key]!=after[key]]
    assert changes==['domains/no_source_damage.py']
    backup=ROOT.parent/'unpack_work/primary_82db_before_no_source_types_v1'
    out=ROOT/'validation/campaign/chapter09_no_source_types_primary_v1/promotion.json'
    assert not backup.exists() and not out.exists()
    shutil.copytree(ROOT/'ark_sim',backup/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert inventory(backup/'ark_sim')==before and core(backup)==OLD
    shutil.copyfile(CAND/'ark_sim/domains/no_source_damage.py',ROOT/'ark_sim/domains/no_source_damage.py')
    assert inventory(ROOT/'ark_sim')==after and core(ROOT)==NEW
    out.parent.mkdir(parents=True)
    out.write_bytes((json.dumps({'passed':True,'primary_before':OLD,'primary_after':NEW,'changed_files':changes,
        'before':before,'after':after,'backup':str(backup),'own_suite_sha':sha(suite_path),
        'own_baseline_sha':sha(baseline_path),'independent_peer_sha':sha(peer_path),
        'scope':'Explicit no-source ARTS/PHYSICAL and NORMAL metadata only; pure formulas remain content-owned. Old stage evidence retains original runtime identity.',
        'peer_extra_failed_fixture_scope_preserved':peer.get('pending',[])},indent=2)+'\n').encode('utf8'))
    print(json.dumps({'passed':True,'core':NEW,'promotion_sha':sha(out)}))


if __name__=='__main__':main()
