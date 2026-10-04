"""Integrate frozen event storage and unlimited projectiles on M26 ancestor."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3];WORK=ROOT.parent/'unpack_work';OUT=WORK/'campaign_m29_storage_projectile_candidate'
REPORT=ROOT/'validation/campaign/m29_integration'
SOURCES={'base':(WORK/'campaign_m26_decision_eligibility_candidate','7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe'),
 'storage':(WORK/'campaign_m27_event_intern_candidate','75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90'),
 'projectile':(WORK/'campaign_m28_unlimited_projectile_candidate','cb0e7a97a2621aaf4b14dc942181686906733acbcc61f6a5a23ebae9448e997b')}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):
 code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
 return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
 for root,pin in SOURCES.values():
  if core(root)!=pin:raise ValueError('Frozen integration input drift')
 if OUT.exists():raise ValueError('Fresh integration path required')
 shutil.copytree(SOURCES['storage'][0]/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 base=SOURCES['base'][0];incoming=SOURCES['projectile'][0];changes=[]
 for p in sorted((incoming/'ark_sim').rglob('*')):
  if p.suffix not in ('.py','.json') or not p.is_file():continue
  rel=p.relative_to(incoming);old=base/rel;current=OUT/rel
  if old.exists() and sha(old)==sha(p):continue
  if current.exists() and (not old.exists() or sha(current)!=sha(old)):
   raise ValueError('Unreviewed overlapping feature file: '+str(rel))
  current.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,current)
  changes.append({'path':rel.as_posix(),'base_sha256':sha(old) if old.exists() else None,'incoming_sha256':sha(p),'result_sha256':sha(current)})
 offline=base/'ark_emulator/levels/packs/level_main_00-01.json';target=OUT/'ark_emulator/levels/packs/level_main_00-01.json'
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(offline,target)
 report={'schema':'ark-sim/storage-unlimited-integration/v1','base_cores':{k:p for k,(_,p) in SOURCES.items()},'changes':changes,
  'candidate':str(OUT),'implementation':core(OUT),'conflicts':[],'formal_approved':False,'actual_game_accuracy_verified':False}
 REPORT.mkdir(parents=True,exist_ok=True);(REPORT/'composition.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
 print(json.dumps({'core':report['implementation'],'changed_projectile_files':len(changes)}))


if __name__=='__main__':main()
