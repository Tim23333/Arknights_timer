"""Combine frozen elementalV3 and promoted no-source types without rebinding evidence."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT.parent/'unpack_work/campaign_elemental_v3_candidate'
OUT=ROOT.parent/'unpack_work/campaign_elemental_no_source_v1_candidate'
CORE='f9079a62d3dd1d964b75620bfe5366e28a4cea4754945d868b0e4cf335cd4c1b'
PRIMARY='5c729384f50e078bd3d3ac9d211360b17bc486588770914efe92ef5b4e983826'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core(root):
    return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()


def main():
    assert core(BASE)==CORE and core(ROOT)==PRIMARY and not OUT.exists()
    shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    target=OUT/'ark_sim/domains/no_source_damage.py'
    shutil.copyfile(ROOT/'ark_sim/domains/no_source_damage.py',target)
    identity=core(OUT)
    folder=ROOT/'validation/campaign/chapter09_joint_v1';folder.mkdir(parents=True,exist_ok=False)
    report={'core':identity,'elemental_parent':CORE,'no_source_parent':PRIMARY,
        'scope':'Mechanical one-file no-source merge into frozen elementalV3; no old proof migrated',
        'files':{str(path.relative_to(OUT)).replace('\\','/'):sha(path) for path in (OUT/'ark_sim').rglob('*') if path.is_file() and path.suffix in ('.py','.json')},
        'required':['Actual FIRE on_break no-source composition','own full/base','fresh combined independent peer'],
        'promoted':False}
    (folder/'merge.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps({'core':identity,'changed_from_elemental':1,'promoted':False}))


if __name__=='__main__':main()
