"""Fresh generic authored tile-field candidate on frozen M27."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate';OUT=ROOT.parent/'unpack_work/campaign_m31_tile_field_candidate'
PIN='75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90'


def main():
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    if subprocess.check_output([sys.executable,'-c',code,str(BASE)],cwd=BASE,text=True).strip()!=PIN:raise ValueError('Frozen tile-field ancestor changed')
    if OUT.exists():raise ValueError('Fresh candidate required')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    source=BASE/'ark_emulator/levels/packs/level_main_00-01.json';target=OUT/'ark_emulator/levels/packs/level_main_00-01.json'
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    print(str(OUT))


if __name__=='__main__':main()
