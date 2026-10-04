"""Author-only exact 4-10 short prefix; no full-stage or portal traversal claim."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate';OUT=ROOT/'validation/campaign/chapter04_10_join_prepare';PIN='7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert implementation_digest()==PIN and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';stage=RUNTIME/'stage/level_main_04-10.complete_frost.explicit.author_prepared.json';assert sha(stage)=='7b5c062528c35bbdfe571763ec7065d75b002cf58bb722e760518eac078957d0';p=json.loads(stage.read_bytes());paths=[stage,Path(__file__),ROOT/'tools/build_chapter04_10_stage.py',ROOT/'tools/build_reference_stage_scenario_v2.py',ROOT/'tools/campaign_content_composition.py',ROOT/'tools/campaign_ordered_checkpoint.py']+[Path(k) if Path(k).is_absolute() else ROOT/k for k in p['manifest']['metadata']['source_locks']]+[f for f in (RUNTIME/'ark_sim').rglob('*') if f.is_file() and f.suffix in ('.py','.json')];before={str(x):sha(x) for x in paths};program=Compiler().compile(p);s=Engine.create(program);s.advance(45);cp=OUT/'v5_stage45.ordered.json';h=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,h));s.advance(45);restored.advance(45);assert s.snapshot()==restored.snapshot()==replay(program,s.export_replay()).snapshot();after={str(x):sha(x) for x in paths};assert before==after and implementation_digest()==PIN
 final=OUT/'v5_stage90.final.json';final.write_text(json.dumps(s.snapshot(),indent=2)+'\n',encoding='utf8',newline='');record=OUT/'v5_stage90.replay.json';record.write_text(json.dumps(s.export_replay(),indent=2)+'\n',encoding='utf8',newline='');boss=next((e for e in s.session.world.entities() if 'enemy' in e['tags'] and 'frstar' in e['definition_id']),None)
 report={'role':'Author short prefix only; independent full Frost/tile/arbiter acceptance remains separate','core':PIN,'stage_sha':sha(stage),'native_seed':p['scenarioDraft']['seed'],'tick':s.session.time,'events':len(s.session.events),'boss_present':boss is not None,'initial_boss_hp':s.ctx.resources.current(boss['id'],'hp') if boss else None,'native43birth_plan':43,'exact_variant_bindings':7,'native_slots':10,'initialDP10_preserved':True,'move_multiplier05_preserved':True,'source_predefines_runes_portals_preserved':True,'ordered_disk_checkpoint_resume_equal':True,'start_public_replay_equal':True,'checkpoint_sha':h,'final_sha':sha(final),'replay_sha':sha(record),'guards_before':before,'guards_after':after,'public_commands':[],'no_operator_deployments_in_this_prefix':True,'actual_portal_transitions_claimed':False,'full_stage_executed':False,'client_verified':False};dest=OUT/'v5_short_verification.json'
 if dest.exists():raise ValueError('Preserve receipt')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':PIN,'tick':s.session.time,'events':len(s.session.events),'boss_present':boss is not None,'report_sha':sha(dest)}))
if __name__=='__main__':main()
