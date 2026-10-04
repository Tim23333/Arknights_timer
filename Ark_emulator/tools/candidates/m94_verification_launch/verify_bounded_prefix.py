"""Complete-event disk prefix with real public commands, CP and replay equality."""
import argparse,gc,hashlib,importlib.util,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
PIN='cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def comparable(o):return {k:o[k] for k in ('snapshot','events','event_count','continuation_state')}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ticks',type=int,default=4651);ap.add_argument('--label',required=True);ap.add_argument('--launch',type=Path,default=OUT/'runthrough_launch.public_v2.prepared.json');args=ap.parse_args();base=OUT/args.label
 if Path(args.label).name!=args.label or base.with_suffix('.verification.json').exists() or base.with_suffix('.active.jsonl').exists():raise ValueError('Fresh direct basename only')
 assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
 launch=json.loads(args.launch.read_bytes());package=Path(launch['package']);commands=Path(launch['commands']);helperfile=Path(launch['helper']);assert sha(package)==launch['package_sha'] and sha(commands)==launch['commands_sha'] and sha(helperfile)==launch['helper_sha']
 spec=importlib.util.spec_from_file_location('m94_prefix_helper',helperfile);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 paths=[package,commands,helperfile,Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py'];pending=[helper];seen=set()
 while pending:
  m=pending.pop()
  if id(m) in seen:continue
  seen.add(id(m))
  if getattr(m,'__file__',None):paths.append(Path(m.__file__))
  pending += [getattr(m,k) for k in ('_v12','_v13') if hasattr(m,k)]
 paths += [p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
 p=json.loads(package.read_bytes());paths += [Path(k) if Path(k).is_absolute() else ROOT/k for k in p['manifest']['metadata']['source_locks']];paths=list(dict.fromkeys(paths));before={str(p):sha(p) for p in paths}
 program=Compiler().compile(p);sim=Engine.create(program,event_journal_path=base.with_suffix('.active.jsonl'));schedule=[c for c in json.loads(commands.read_bytes()) if c['at']<args.ticks]
 for command in schedule:sim.submit({k:v for k,v in command.items() if k!='at'},at=command['at'])
 split=min(800,args.ticks//2);checkpoint=None;started=time.monotonic()
 while sim.session.time<args.ticks:
  target=min(sim.session.time+100,args.ticks)
  if checkpoint is None and sim.session.time<split<=target:target=split
  sim.session.advance(target-sim.session.time)
  if sim.session.time==split:checkpoint=helper.write_checkpoint(sim,base.with_suffix('.checkpoint.json'));helper.load_checkpoint(checkpoint)
  print(json.dumps({'phase':'prefix','tick':sim.session.time,'events':len(sim.session._events._records),'elapsed_seconds':round(time.monotonic()-started,2)}),flush=True)
 actual=helper.observations(sim,base.with_suffix('.events.jsonl'));record=sim.export_replay();life=sim.ctx.resources.current('system/battle','life');state=sim.ctx.state();end=sim.session.time;del sim;gc.collect()
 restored=Engine.restore(program,helper.load_checkpoint(checkpoint));restored.session.advance(end-restored.session.time);continued=helper.observations(restored,base.with_suffix('.continued.events.jsonl'));assert comparable(actual)==comparable(continued);del restored;gc.collect()
 repeated=replay(program,record,event_journal_path=base.with_suffix('.replay.active.jsonl'));replayed=helper.observations(repeated,base.with_suffix('.replayed.events.jsonl'));assert comparable(actual)==comparable(replayed);del repeated;gc.collect()
 accepted=[];rejected=[];triggers=0;none_count=0
 with Path(actual['export']['path']).open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line)
   if e['type']=='command.accepted':accepted.append(e)
   elif e['type']=='command.rejected':rejected.append(e)
   elif e['type']=='field.triggered':triggers+=1
   elif e['type']=='damage.accepted' and e['payload'].get('source') is None:none_count+=1
 units=sorted({e['payload']['action']['entity'] for e in accepted if e['payload']['action']['action']=='deploy'});after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==PIN
 report={'core':PIN,'stage_sha':sha(package),'commands_sha':sha(commands),'native_seed':p['scenarioDraft']['seed'],'end_tick':end,'source_births_expected':49,'all12_first_deploy_accepted':set(units)==set(p['scenarioDraft']['roster']),'accepted_units':units,'accepted_commands':accepted,'rejected_commands':rejected,'base_life_final':life,'state':state,'field_trigger_count':triggers,'NoSource_packet_count':none_count,'observations':comparable(actual),'journal':actual['export'],'continued_journal':continued['export'],'replayed_journal':replayed['export'],'checkpoint':checkpoint,'checkpoint_resume_equal':True,'start_public_replay_equal':True,'guards_before':before,'guards_after':after,'whole_stage_executed':False,'client_verified':False}
 dest=base.with_suffix('.verification.json');dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'tick':end,'accepted_unique_deploys':len(units),'events':actual['event_count'],'report_sha':sha(dest)}),flush=True)
if __name__=='__main__':main()
