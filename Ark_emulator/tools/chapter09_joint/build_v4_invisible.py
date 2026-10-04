"""Mechanical frozen cache+elemental/no-source and optional invisible merge."""
import json
import shutil
from pathlib import Path
from tools.chapter09_joint.build_v1 import ROOT,core,sha

BASE=ROOT.parent/'unpack_work/campaign_elemental_no_source_v3_candidate'
SIGHT=ROOT.parent/'unpack_work/campaign_invisible_v1_candidate'
OUT=ROOT.parent/'unpack_work/campaign_c9_foundation_v4_candidate'


def main():
    assert core(BASE)=='94d5b7a00c27383ea75b58885bafec1f02be6ad3f69d85f70f54af30a0fe03b0'
    assert core(SIGHT)=='4321a27f07d44574a5ce5f6ea740dced097e02868bd28a4580f529853c546563'
    assert sha(BASE/'ark_sim/domains/selection.py')==sha(ROOT/'ark_sim/domains/selection.py')
    assert not OUT.exists()
    shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(SIGHT/'ark_sim/domains/selection.py',OUT/'ark_sim/domains/selection.py')
    folder=ROOT/'validation/campaign/chapter09_foundation_v4';folder.mkdir(parents=True,exist_ok=False)
    identity=core(OUT)
    value={'core':identity,'parents':[core(BASE),core(SIGHT)],'primary_parent':core(ROOT),
        'files':{str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')},
        'scope':'One-file optional invisibility merge into cache/elemental/no-source candidate; no old gate migration',
        'own_full_pending':True,'own_baseline_pending':True,'independent_joint_pending':True,'promoted':False}
    (folder/'merge.json').write_bytes((json.dumps(value,indent=2)+'\n').encode())
    print(json.dumps({'core':identity,'promoted':False}))


if __name__=='__main__':main()
