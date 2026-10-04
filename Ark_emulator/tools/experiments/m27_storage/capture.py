import sys,json,hashlib,argparse,time,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--core',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();runtime=a.runtime.resolve();sys.path.insert(0,str(runtime))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
PACKAGE=ROOT/'packages/campaign/runthrough/level_main_01-12.m26_decision.life99999.json';COMMANDS=ROOT/'scenarios/campaign/chapter01/01-12/commands.runthrough_exploratory_v2.json';guards=[PACKAGE,COMMANDS,Path(__file__),runtime/'ark_sim/rules/contracts.json',runtime/'ark_sim/content/presets/ark_standard.json'];before={str(p.resolve()):sha(p) for p in guards};assert implementation_digest()==a.core and Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim';begun=time.time();p=json.loads(PACKAGE.read_bytes());s=Engine.create(Compiler().compile(p),seed=p['scenarioDraft']['seed'])
for command in json.loads(COMMANDS.read_bytes()):
 c=dict(command);tick=c.pop('at');s.submit(c,at=tick)
s.advance(300);a.output.parent.mkdir(parents=True,exist_ok=True);events_path=a.output.with_suffix('.events.jsonl');event_hash=hashlib.sha256()
with events_path.open('wb') as f:
 for e in s.session.events:
  row=(json.dumps(thaw(e),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8');f.write(row);event_hash.update(row)
state={'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'random':s.session.random.snapshot(),'state':s.ctx.state(),'time':s.session.time,'quantum':s.session.quantum};state_path=a.output.with_suffix('.state.json');state_path.write_text(json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n',encoding='utf8');after={str(p.resolve()):sha(p) for p in guards};assert before==after and implementation_digest()==a.core
report={'schema':'ark-sim/m27-full-value-capture/v1','core_start':a.core,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,'package_sha256':sha(PACKAGE),'commands_sha256':sha(COMMANDS),'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'source_before':before,'source_after':after,'tick':300,'events':len(s.session.events),'events_path':str(events_path),'events_sha256':event_hash.hexdigest(),'state_path':str(state_path),'state_sha256':sha(state_path),'cache':s.session._events._payload_interner.statistics() if hasattr(s.session._events,'_payload_interner') else None,'elapsed_seconds':time.time()-begun,'values_dropped':False};a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'events':len(s.session.events),'elapsed':report['elapsed_seconds'],'raw_events_sha256':report['events_sha256'],'state_sha256':report['state_sha256']}),flush=True)
