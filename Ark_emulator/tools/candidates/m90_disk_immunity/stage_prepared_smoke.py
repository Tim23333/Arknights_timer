"""Actual prepared stage short prefix; explicitly no full-stage/source signoff."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate';OUT=ROOT/'validation/campaign/m91_complete_c4'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 stage=RUNTIME/'stage/level_main_04-09.m92.first_hit.source_circle.prepared.json';assert sha(stage)=='7e0e3c842b7f3af8d561a4d45f5f834ffc560ec2eb489bdd5d20147a36da19f9'
 assert implementation_digest()=='e370d26ed84e5ac95feea9af51ac038f57ab7b7c22d943dd2116a99b50006feb'
 paths=[stage,ROOT/'packages/campaign/chapter04_dmage/module.combat_guard.reference.json',ROOT/'tools/build_chapter04_09_stage.py',ROOT/'tools/campaign_ordered_checkpoint.py',Path(__file__)]
 paths += [p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')]
 before={str(p):sha(p) for p in paths};program=Compiler().compile(json.loads(stage.read_bytes()));s=Engine.create(program,seed=910409);s.advance(45)
 cp=OUT/'prepared_stage45.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(45);r.advance(45);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
 after={str(p):sha(p) for p in paths};assert before==after
 final=OUT/'prepared_stage90.final.json';final.write_text(json.dumps(s.snapshot(),indent=2)+'\n',encoding='utf8',newline='')
 report={'core':implementation_digest(),'stage_sha256':sha(stage),'actual_tick':s.session.time,'events':len(s.session.events),'checkpoint_resume_equal':True,'public_start_replay_equal':True,'guards_before':before,'guards_after':after,'checkpoint_sha256':h,'final_sha256':sha(final),'public_commands':s.export_replay(),'source_module_review':'M92 guard prepared pending Root independent receipt','fixed12_deployment':'No deployments in this short prefix; package roster fixed12','whole_stage_executed':False,'client_verified':False}
 p=OUT/'prepared_stage_smoke.json';p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'tick':s.session.time,'events':len(s.session.events),'report_sha256':sha(p)}))
if __name__=='__main__':main()
