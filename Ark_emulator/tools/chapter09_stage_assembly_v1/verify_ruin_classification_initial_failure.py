"""Ruin gameplay remains intact while source devices do not become wave enemies."""
import argparse,json,hashlib,os,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from tools.chapter09_stage_assembly_v1.providers import providers
    path=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v2.life99999.json';p=json.loads(path.read_bytes());ruin=deepcopy(next(x for x in p['definitions'] if x['id']=='unit/ch9/pillar/ruin'))
    d={'schemaVersion':2,'entities':[ruin],'scenarioDraft':{'id':'scene/ruin/classification','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':ruin['id'],'instanceAlias':'ruin','position':{'row':1,'col':2}}]}}
    objective=deepcopy(d);objective['scenarioDraft']['objectives']={'type':'waves','life_resource':'life'};s=Engine.create(Compiler(providers=providers()).compile(objective),providers=providers());s.advance(1);assert s.ctx.state()['finished'] and s.ctx.alive('ruin') and s.ctx.resources.current('ruin','hp')==100
    mover={'id':'unit/ruin/test/mover','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':131,'atk':0,'def':0,'mres':0,'move_speed':1,'block_occupancy':1}},'resources':{'hp':{'initial':131,'capacity':131,'role':'health'}},'spatial':{}}};d['entities'].append(mover)
    route={'startPosition':{'row':1,'col':2},'endPosition':{'row':1,'col':4},'motionMode':0,'checkpoints':[]}
    d['scenarioDraft']['initialEntities'] += [{'definition':mover['id'],'instanceAlias':'mover'+str(i),'position':{'row':1,'col':2},'route':route} for i in range(4)]
    s=Engine.create(Compiler(providers=providers()).compile(d),providers=providers());s.advance(1);s.ctx.spatial.blocking();refs=[s.session.world.resolve('mover'+str(i)) for i in range(4)];block=s.session.world.resolve('ruin');assert [s.ctx.spatial.blocked_by(x) for x in refs]==[block,block,block,None]
    q=Path(os.environ['ARKSIM_RUN_DIR'])/'classification.checkpoint.json';q.write_text(json.dumps(s.checkpoint()),encoding='utf8');r=Engine.restore(s.program,json.loads(q.read_bytes()),providers=providers());s.advance(10);r.advance(10);h=replay(s.program,s.export_replay(),providers=providers());assert s.checkpoint()==r.checkpoint()==h.checkpoint()
    death_before=s.ctx.state()['kills'];s.ctx.lifecycle.retire('ruin','dead');assert s.ctx.state()['kills']==death_before
    result={'passed':True,'actual_exit':0,'core':implementation_digest(),'package_sha':hashlib.sha256(path.read_bytes()).hexdigest(),'native_zero_enemy_wave_completion_while_ruin_alive':True,'device_side1_category4_HP100_block3_preserved':True,'actual_four_movers_first3blocked':True,'device_death_not_native_enemy_kill':True,'CPP_head_full_equal':True,'checkpoint_sha':hashlib.sha256(q.read_bytes()).hexdigest(),'whole_stage':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
