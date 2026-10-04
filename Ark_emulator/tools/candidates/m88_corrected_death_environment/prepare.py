"""Reproducible corrected retirement+death sequence combination."""
import json,shutil
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.candidates.m87_retire_compatibility.prepare import core
BASE=ROOT.parent/'unpack_work/campaign_m87_retire_compatibility_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m85_death_sequence_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m88_corrected_death_environment_candidate'


def main():
    if OUT.exists():raise ValueError('Preserve existing candidate')
    assert core(BASE)=='60053a72055f403314c1e679f38aaba7edf970001439854c014f438e0fa212be'
    assert core(INCOMING)=='b2ffe94256fbf31d85e3dda6ed4f6d7f7a84e036e532b4bd4b80a911247a81e2'
    shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(INCOMING/'ark_sim/domains/death_projectiles.py',OUT/'ark_sim/domains/death_projectiles.py')
    assert core(OUT)=='3577e4cd2621218cbb819f3c4b21f32922f562c9176d26ab80681bc91f587af1'
    print(json.dumps({'core':core(OUT),'changed':['domains/death_projectiles.py']}))


if __name__=='__main__':main()
