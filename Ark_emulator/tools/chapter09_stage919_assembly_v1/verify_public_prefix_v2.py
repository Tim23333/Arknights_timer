"""Execute initial fixed-squad and card attempts with full CP/public-head values."""
import argparse,hashlib,json,os,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--core',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import thaw,digest
    from tools.chapter09_stage919_assembly_v1.providers_v2 import providers
    assert implementation_digest()==args.core
    package=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v2.life99999.json';commands=ROOT/'scenarios/campaign/chapter09/level_main_09-17/public_plan_v1_finite/commands.json';p=json.loads(package.read_bytes());cmds=json.loads(commands.read_bytes());p['scenarioDraft']['commands']=cmds
    source=[package,commands,Path(__file__),ROOT/'tools/chapter09_stage919_assembly_v1/providers_v2.py']+[x for x in (runtime/'ark_sim').rglob('*') if x.is_file() and x.suffix in ('.py','.json')];guard=lambda:{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in source};before=guard()
    program=Compiler(providers=providers()).compile(p);s=Engine.create(program,providers=providers(),seed=program.scenario['seed']);s.advance(91);q=Path(os.environ['ARKSIM_RUN_DIR'])/'public91.checkpoint.json';q.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(program,json.loads(q.read_bytes()),providers=providers());s.advance(91);r.advance(91);h=replay(program,s.export_replay(),providers=providers());assert s.checkpoint()==r.checkpoint()==h.checkpoint();after=guard();assert before==after
    outcomes=[thaw(e) for e in s.session.events if e['type'] in ('command.accepted','command.rejected')];assert len(outcomes)==2
    assert outcomes[0]['type']=='command.accepted' and outcomes[0]['payload']['action']['alias']=='c9_myrtle'
    assert outcomes[1]['type']=='command.accepted' and outcomes[1]['payload']['action']['alias']=='c9_device1'
    device=s.session.world.resolve('c9_device1');assert not s.ctx.alive(device)
    result={'schema':'ark-sim/c9-919-public-prefix/v2','passed':True,'actual_exit':0,'core':args.core,'package_sha':before[str(package)],'commands_sha':before[str(commands)],'end_tick':182,'CPP_head_full_equal':True,'checkpoint_sha':hashlib.sha256(q.read_bytes()).hexdigest(),'final_checkpoint_digest':digest(s.checkpoint()),'actual_outcomes':outcomes,'device_actual_retired':True,'stock_remaining':s.ctx.resources.current('system/battle','stock_ch9_demolition'),'dp_actual':s.ctx.resources.current('system/battle','dp'),'source_guard_start':before,'source_guard_end':after,'source_guard_equal':True,'whole_stage':False,'client_verified':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'outcomes':2,'device_retired':True}));return 0


if __name__=='__main__':raise SystemExit(main())
