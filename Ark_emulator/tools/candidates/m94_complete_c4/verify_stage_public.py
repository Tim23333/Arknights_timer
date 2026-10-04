"""Real 4-9 public deploy/skill/withdraw prefix with ordered CP and replay."""
import argparse,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate';OUT=ROOT/'validation/campaign/m94_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from ark_sim.contracts import thaw
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--expected-core',required=True);ap.add_argument('--ticks',type=int,default=1600);args=ap.parse_args();assert implementation_digest()==args.expected_core
 stage=RUNTIME/'stage/level_main_04-09.m92.first_hit.source_circle.life99999.json';plan=OUT/'public_fixed12_plan.compact.prepared.json';p=json.loads(stage.read_bytes());schedule=json.loads(plan.read_bytes());s=p['scenarioDraft'];assert s['resources']['life']['initial']==s['resources']['life']['capacity']==99999 and len(s['roster'])==12 and sum(t['tileKey']=='tile_volcano' for t in s['map']['tiles'])==8
 assert s['parameters']['deploy_capacity']==8
 paths=[stage,plan,Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter04_dmage/module.combat_guard.reference.json']+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')];before={str(p):sha(p) for p in paths}
 program=Compiler().compile(p);sim=Engine.create(program)
 commands=[c for c in schedule['commands'] if c['at']<args.ticks]
 for command in commands:sim.submit({k:v for k,v in command.items() if k!='at'},at=command['at'])
 split=args.ticks//2;sim.advance(split);cp=OUT/f'compact_public{split}.ordered.json';h=write_ordered(cp,sim.checkpoint());restored=Engine.restore(program,load_bound(cp,h));sim.advance(args.ticks-split);restored.advance(args.ticks-split);assert sim.snapshot()==restored.snapshot()==replay(program,sim.export_replay()).snapshot()
 after={str(p):sha(p) for p in paths};assert before==after
 events=thaw(tuple(sim.session.events));final=OUT/f'compact_public{args.ticks}.final.json';final.write_text(json.dumps(sim.snapshot(),indent=2)+'\n',encoding='utf8',newline='');replayfile=OUT/f'compact_public{args.ticks}.replay.json';replayfile.write_text(json.dumps(sim.export_replay(),indent=2)+'\n',encoding='utf8',newline='')
 report={'core':args.expected_core,'stage_sha':sha(stage),'plan_sha':sha(plan),'source_seed':s['seed'],'ticks':sim.session.time,'events':len(events),'commands':commands,'command_events':[e for e in events if e['type'].startswith('command.')],'deployment_events':[e for e in events if e['type'].startswith('deploy.')],'field_triggers':sum(e['type']=='field.triggered' for e in events),'NoSource_packets':[e for e in events if e['type']=='damage.accepted' and e['payload'].get('source') is None],'actual_short_prefix':True,'all12_deployed':False,'checkpoint_resume_equal':True,'start_public_replay_equal':True,'guard_before':before,'guard_after':after,'checkpoint_sha':h,'final_sha':sha(final),'replay_sha':sha(replayfile),'whole_stage_executed':False,'client_verified':False}
 actual_deploys=[e for e in events if e['type']=='command.accepted' and e['payload']['action']['action']=='deploy'];report['accepted_deploy_units']=sorted({e['payload']['action']['entity'] for e in actual_deploys});report['all12_deployed']=set(report['accepted_deploy_units'])==set(s['roster']);report['base_life_final']=sim.ctx.resources.current('system/battle','life')
 dest=OUT/f'compact_public{args.ticks}.verification.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'events':len(events),'tick':sim.session.time,'accepted_unique_deploys':len(report['accepted_deploy_units']),'report_sha':sha(dest)}))
if __name__=='__main__':main()
