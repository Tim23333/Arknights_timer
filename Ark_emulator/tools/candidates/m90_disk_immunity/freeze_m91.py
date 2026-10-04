"""Archive exact reviewed composite bytes without promoting or mutating parents."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];U=ROOT.parent/'unpack_work';OUT=ROOT/'validation/campaign/m91_complete_c4'
sys.path.insert(0,str(ROOT))
from tools.candidates.m79_rebirth_environment.prepare import core,sha
def main():
 candidate=U/'campaign_m91_complete_c4_candidate';pin='e370d26ed84e5ac95feea9af51ac038f57ab7b7c22d943dd2116a99b50006feb'
 assert core(candidate)==pin
 verification=OUT/'verification.json';assert sha(verification)=='d658552db861c6a09e7937eedf29f6540f0b24e1fc87f7482a0cb979f6263225'
 report=json.loads(verification.read_bytes());assert report['exitcode']==0 and len(report['cases'])==246 and all(c['outcome']=='passed' for c in report['cases'])
 for name,digest in report['guards_after'].items():assert sha(Path(name))==digest,name
 target=OUT/'source_files'
 if target.exists() or (OUT/'freeze.json').exists():raise ValueError('Preserve prior freeze')
 archive={}
 for p in sorted((candidate/'ark_sim').rglob('*')):
  if p.is_file() and p.suffix in ('.py','.json'):
   name=p.relative_to(candidate);dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);archive[name.as_posix()]=sha(dest);assert p.read_bytes()==dest.read_bytes()
 contracts=json.loads((candidate/'ark_sim/rules/contracts.json').read_bytes());assert len({r['id'] for r in contracts['contracts']})==len(contracts['contracts'])
 paths=[OUT/'composition.json',verification,OUT/'verification_run2.log',ROOT/'validation/campaign/m90_disk_immunity/composition.json',*Path(__file__).parent.glob('*.py')]
 stage=candidate/'stage/level_main_04-09.first_hit.source_circle.json'
 frozen={'core':pin,'candidate':str(candidate),'source_files':archive,'catalog_count':len(contracts['contracts']),'proof_files':{str(p):sha(p) for p in paths},'actual_passed':246,'stage_history':{'path':str(stage),'sha256':sha(stage),'policy':{'demon_phase':'first_hit','range':'source_circle'},'known_content_gap':'Old dmage normal source selector finite blocked priority loses to taunt20; replacement wrapper pending'},'whole_stage_executed':False,'client_verified':False,'promotion':False}
 (OUT/'freeze.json').write_text(json.dumps(frozen,indent=2)+'\n',encoding='utf8',newline='')
 print(json.dumps({'core':pin,'source_files':len(archive),'catalog_count':len(contracts['contracts']),'freeze_sha256':sha(OUT/'freeze.json')}))
if __name__=='__main__':main()
