"""Add public roster membership enforcement to a fresh isolated candidate."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent/'unpack_work/campaign_m21_integration_candidate'
OUT = ROOT.parent/'unpack_work/campaign_m23_roster_candidate'
PIN = 'c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e'


def main():
    command = 'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    if subprocess.check_output([sys.executable, '-c', command, str(BASE)], cwd=BASE, text=True).strip() != PIN:
        raise ValueError('frozen M21 parent drift')
    if OUT.exists() or OUT.parent.resolve() != BASE.parent.resolve(): raise ValueError('fresh named candidate required')
    shutil.copytree(BASE/'ark_sim', OUT/'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    path = OUT/'ark_sim/adapters/api.py'; source = path.read_text(encoding='utf8')
    old = '        definition_id = action.get("entity", action.get("definition"))\n        from ark_sim.domains.deployment import prepare, record'
    new = '''        definition_id = action.get("entity", action.get("definition"))
        if "roster" in self.program.scenario and definition_id not in self.program.scenario["roster"]:
            raise ValueError("definition is not in the selected scenario roster")
        from ark_sim.domains.deployment import prepare, record'''
    if source.count(old) != 1: raise ValueError('unexpected parent deployment entry')
    path.write_text(source.replace(old, new), encoding='utf8', newline='\n')
    offline = BASE/'ark_emulator/levels/packs/level_main_00-01.json'
    target = OUT/'ark_emulator/levels/packs/level_main_00-01.json'; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(offline, target)
    print(subprocess.check_output([sys.executable, '-c', command, str(OUT)], cwd=OUT, text=True).strip())


if __name__ == '__main__': main()
