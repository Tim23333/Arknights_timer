"""Byte-exact M91 archived-source reconstruction into a fresh direct child."""
import argparse,json,shutil,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];U=(ROOT.parent/'unpack_work').resolve();OUT=ROOT/'validation/campaign/m91_complete_c4'
PIN='12f5e9cf991187757b13bdc2277f43c18850b7da9ac45d8c6b7b1ba2b8d93fbe'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('directory');args=ap.parse_args();target=(U/args.directory).resolve()
 if target.parent!=U or target.exists():raise ValueError('Fresh direct child only')
 freeze=OUT/'freeze.json';assert sha(freeze)==PIN;report=json.loads(freeze.read_bytes())
 for name,pin in report['source_files'].items():
  p=OUT/'source_files'/name;assert sha(p)==pin;assert name.startswith('ark_sim/')
 for name,pin in report['source_files'].items():
  p=target/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OUT/'source_files'/name,p);assert sha(p)==pin
 fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(target/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(U/'campaign_m88_corrected_death_environment_candidate'/fixture,target/fixture)
 code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
 p=subprocess.run([sys.executable,'-c',code,str(target)],capture_output=True,text=True,check=True);assert p.stdout.strip()==report['core']
 print(json.dumps({'core':report['core'],'directory':str(target),'source_files':len(report['source_files'])}))
if __name__=='__main__':main()
