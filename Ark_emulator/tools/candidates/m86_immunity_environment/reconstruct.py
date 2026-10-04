"""Reconstruct frozen M86 bytes into a fresh ignored root without rewriting proof."""
import json,hashlib,shutil,subprocess,sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];UNPACK=(ROOT.parent/'unpack_work').resolve();BASE=UNPACK/'campaign_m88_corrected_death_environment_candidate';REPORT=ROOT/'validation/campaign/m86_immunity_environment/candidate_final.json';PIN='f42be60faee6d6a2236f6c01b00e8fc3e24176a674a45661cec43170893cf723';CORE='6013ef4e0f94e188391fb2593d681914b95291862acea662f292200bb644a1f6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('directory');a=ap.parse_args();dest=(UNPACK/a.directory).resolve()
 if dest.parent!=UNPACK or dest.exists():raise ValueError('Fresh direct child required, never overwrite an existing root')
 if sha(REPORT)!=PIN:raise ValueError('Frozen report drift')
 report=json.loads(REPORT.read_bytes());archive=REPORT.parent/'source_files'
 for name,pin in report['changed_files'].items():
  if sha(archive/name)!=pin:raise ValueError('Archived source drift '+name)
 for name,pin in report['source_before'].items():
  if name.replace('\\','/') not in report['changed_files'] and sha(BASE/name)!=pin:raise ValueError('Frozen base drift '+name)
 shutil.copytree(BASE/'ark_sim',dest/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for name in report['changed_files']:
  p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((archive/name).read_bytes())
 baseline=Path('ark_emulator/levels/packs/level_main_00-01.json');(dest/baseline).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/baseline,dest/baseline)
 for name,pin in report['source_before'].items():
  if sha(dest/name)!=pin:raise ValueError('Reconstructed source mismatch '+name)
 code="import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())";run=subprocess.run([sys.executable,'-c',code,str(dest)],capture_output=True,text=True,check=True)
 if run.stdout.strip()!=CORE:raise ValueError('Actual imported core mismatch')
 print(json.dumps({'directory':str(dest),'core':CORE,'source_files':len(report['source_before'])}))
if __name__=='__main__':main()
