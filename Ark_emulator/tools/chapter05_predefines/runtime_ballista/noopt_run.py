"""Original no-opt complete0-1/custom snapshots under an explicitly selected core."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT));import ark_sim
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 assert implementation_digest()==args.expected_core and Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim'
 if args.output.exists():raise ValueError('Preserve noopt snapshot')
 paths=[p for p in (runtime/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]+[Path(__file__),ROOT/'packages/ark_content/level_main_00_01.json',ROOT/'scenarios/level_main_00_01/commands.json',ROOT/'packages/custom/custom_guard.json'];before={str(p):sha(p) for p in paths};cases=[]
 for ruleset,expected in [('ruleset/ark_standard',850),('ruleset/custom_balance',60)]:
  program=Compiler().compile(ROOT/'packages/custom/custom_guard.json',ruleset=ruleset);s=Engine.create(program,seed=123);s.session.advance(30);assert s.ctx.state()['damage_dealt']==expected;cases.append({'case':ruleset,'snapshot':s.snapshot()})
 program=Compiler().compile(ROOT/'packages/ark_content/level_main_00_01.json');s=Engine.create(program,seed=123)
 for c in json.loads((ROOT/'scenarios/level_main_00_01/commands.json').read_bytes()):s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
 s.session.advance(300)
 while not s.ctx.state()['finished'] and s.session.time<10000:
  s.session.advance(150);print(json.dumps({'tick':s.session.time,'kills':s.ctx.state()['kills'],'events':len(s.session.events)}),flush=True)
 assert (s.ctx.state()['kills'],s.ctx.state()['leaks'],s.ctx.state()['pending_waves'])==(11,0,0);cases.append({'case':'complete0-1','snapshot':s.snapshot()});after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==args.expected_core;args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps({'core':args.expected_core,'cases':cases,'guard_before':before,'guard_after':after},ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8',newline='');print(json.dumps({'core':args.expected_core,'output_sha':sha(args.output),'events':len(s.session.events)}),flush=True)
if __name__=='__main__':main()
