"""Reconstruct final M70 from immutable M68 plus verified archived changed bytes."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,subprocess
ROOT=Path(__file__).resolve().parents[3];UNPACK=(ROOT.parent/'unpack_work').resolve();BASE=UNPACK/'campaign_m68_deployment_integrated_candidate';REPORT=ROOT/'validation/campaign/m70_applicability_v2/candidate_final.json';PIN='919d6e0443555b76915ca9682a22170ed344e2a1957c93814422deb1bea71cfd';CORE='0b5a6a6b09cfbb631bd69dd67079814e90bccbe4d5d5737c1d33f869b7fab647'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('directory',help='New direct child of unpack_work; existing roots rejected');a=ap.parse_args();dest=(UNPACK/a.directory).resolve()
 if dest.parent!=UNPACK or dest.exists():raise ValueError('Reconstruction needs a fresh direct child, never overwrite a frozen root')
 if sha(REPORT)!=PIN:raise ValueError('Frozen report drift')
 report=json.loads(REPORT.read_bytes());archive=REPORT.parent/'source_files'
 for name,pin in report['changed_files'].items():
  if sha(archive/name)!=pin:raise ValueError('Archived source drift '+name)
 for name,pin in report['source_before'].items():
  if name.replace('\\','/') not in report['changed_files'] and sha(BASE/name)!=pin:raise ValueError('Frozen base drift '+name)
 shutil.copytree(BASE/'ark_sim',dest/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 for name in report['changed_files']:
  output=dest/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes((archive/name).read_bytes())
 for name,pin in report['source_before'].items():
  if sha(dest/name)!=pin:raise ValueError('Reconstructed source mismatch '+name)
 code="import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())"
 run=subprocess.run([sys.executable,'-c',code,str(dest)],capture_output=True,text=True,check=True)
 if run.stdout.strip()!=CORE:raise ValueError('Reconstructed implementation identity mismatch')
 print(json.dumps({'directory':str(dest),'core':CORE,'source_files':len(report['source_before'])}))
if __name__=='__main__':main()
