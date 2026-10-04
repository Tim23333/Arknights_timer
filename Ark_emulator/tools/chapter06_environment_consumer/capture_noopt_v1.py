"""Actual opt-out observations using explicit imported parent/candidate, unchanged source inputs."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--core',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sys.path.insert(0,str(a.runtime.resolve()));sys.path.insert(1,str(ROOT));from ark_sim import Compiler,Engine;from ark_sim.adapters.api import implementation_digest;assert implementation_digest()==a.core;assert not a.output.exists();cases=[]
 for pkg,rule,ticks,commands in [('packages/custom/custom_guard.json','ruleset/ark_standard',30,None),('packages/custom/custom_guard.json','ruleset/custom_balance',30,None),('packages/ark_content/level_main_00_01.json',None,150,'scenarios/level_main_00_01/commands.json')]:
  program=Compiler().compile(ROOT/pkg,**({'ruleset':rule} if rule else {}));s=Engine.create(program,seed=123)
  if commands:
   for c in json.loads((ROOT/commands).read_bytes()):
    if c['at']<ticks:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
  s.session.advance(ticks);cases.append({'package':pkg,'package_sha':sha(ROOT/pkg),'ruleset':rule,'snapshot':s.snapshot()})
 assert implementation_digest()==a.core;a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps({'core':a.core,'cases':cases},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(a.output),'events':[len(c['snapshot']['events']) for c in cases]}))
if __name__=='__main__':main()
