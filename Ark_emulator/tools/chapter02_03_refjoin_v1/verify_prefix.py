import sys,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';CORE='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter02_03_refjoin_v1';prep=json.loads((OUT/'preparation.json').read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
files=[Path(__file__),OUT/'preparation.json',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/chapter02_03_refjoin_v1/prepare.py']+[Path(p) for p in prep['guard_start']]
for r in prep['results']:files.extend(Path(r[x]) for x in ['native_package','life_package','commands'])
def guard():return {str(p):sha(p) for p in sorted(set(files))}
BEFORE=guard();assert implementation_digest()==CORE
RESULT=[]
for row in prep['results']:
 stage=row['stage'];capture={};directory=OUT/(stage+'.prefix220');directory.mkdir(exist_ok=False)
 try:
  p=json.loads(Path(row['life_package']).read_text(encoding='utf8'));commands=json.loads(Path(row['commands']).read_text(encoding='utf8'))
  s=Engine.create(Compiler().compile(p),seed=p['scenarioDraft']['seed'],event_journal_path=directory/'original.active.jsonl')
  for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
  s.advance(100);cp=directory/'ordered.checkpoint.json';h=write_ordered(cp,s.checkpoint());restored=Engine.restore(s.program,load_bound(cp,h))
  s.advance(120);restored.advance(120);repeated=replay(s.program,s.export_replay())
  checks={'disk_restore_checkpoint_equal':s.checkpoint()==restored.checkpoint(),'public_replay_checkpoint_equal':s.checkpoint()==repeated.checkpoint(),'disk_restore_snapshot_equal':s.snapshot()==restored.snapshot(),'public_replay_snapshot_equal':s.snapshot()==repeated.snapshot(),'disk_restore_events_equal':thaw(tuple(s.session.events))==thaw(tuple(restored.session.events)),'public_replay_events_equal':thaw(tuple(s.session.events))==thaw(tuple(repeated.session.events))}
  capture={'stage':stage,'passed':all(checks.values()),'checks':checks,'core':implementation_digest(),'runtime_module':sys.modules['ark_sim'].__file__,'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint_sha':h,'checkpoint_at':100,'end_tick':220,'events':len(s.session.events),'commands_submitted':len(commands),'command_results':[thaw(e) for e in s.session.events if e['type'] in ['command.accepted','command.rejected']],'state':thaw(s.ctx.state()),'full_stage_executed':False}
  for name,sim in [('original',s),('restored',restored),('public_replay',repeated)]:
   write(directory/(name+'.snapshot.json'),sim.snapshot())
   journal=directory/(name+'.events.jsonl')
   with journal.open('x',encoding='utf8',newline='') as f:
    for e in sim.session.events:f.write(json.dumps(thaw(e),ensure_ascii=False,separators=(',',':'))+'\n')
   capture[name+'_journal_sha']=sha(journal)
  write(directory/'public_replay.json',s.export_replay());write(directory/'verification.json',capture)
  assert all(checks.values()),checks
 except Exception:capture.update(stage=stage,passed=False,error=traceback.format_exc());write(directory/'failure.json',capture)
 RESULT.append(capture)
AFTER=guard();report={'core':implementation_digest(),'results':RESULT,'guards_before':BEFORE,'guards_after':AFTER,'guards_equal':BEFORE==AFTER,'scope':'New author input prefix100 ordered disk CP and220 continuation/replay; same frozen old commands and definitions, no old CP consumed and no full stage started.'}
write(OUT/'prefix_verification.json',report);print(json.dumps({'results':[{'stage':x['stage'],'passed':x['passed'],'events':x.get('events'),'error':x.get('error')} for x in RESULT],'guards_equal':BEFORE==AFTER,'sha':sha(OUT/'prefix_verification.json')}))
