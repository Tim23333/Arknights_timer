"""Actual Holy/Shadow input-target obstacle combat, preserving range masks."""
import argparse
from copy import deepcopy
import hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import thaw,digest
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter09_stage_assembly_v1.providers_v5 import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    core='2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0';assert implementation_digest()==core
    result={'core':core,'passed':False,'cases':[]};folder=ROOT/'packages/campaign/chapter09_stage_models'
    def create(version,name):
        p=json.loads((folder/f'level_main_09-16.native_draft.v{version}.life99999.json').read_bytes())
        unit=next(d for d in p['definitions'] if d['kind']=='entity' and d['id'].startswith('unit/ch9/coupled/'+name+'/'))
        route={'startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':4},'motionMode':0,'checkpoints':[]}
        p['scenarioDraft']={'id':'scene/ch9/input/'+str(version)+name,'ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':6},'objectives':{},'initialEntities':[{'definition':'unit/ch9/pillar/ruin','instanceAlias':'ruin','position':{'row':2,'col':2}},{'definition':unit['id'],'instanceAlias':'enemy','position':{'row':2,'col':2},'route':route}]}
        program=Compiler(providers=providers()).compile(p);return Engine.create(program,providers=providers())
    try:
        for name in ('duholy','dushdo'):
            old=create(4,name);old.advance(100);assert old.ctx.resources.current('ruin','hp')==100 and old.ctx.spatial.blocked_by('enemy') is not None
            assert not [e for e in old.session.events if e['type']=='ability.started' and '/combat' in e['payload'].get('ability','')]
            a=create(5,name);a.advance(8);q=Path(os.environ['ARKSIM_RUN_DIR'])/(name+'.checkpoint.json');pin=write_ordered(q,a.checkpoint());b=Engine.restore(a.program,load_bound(q,pin),providers=providers());a.advance(112);b.advance(112);h=replay(a.program,a.export_replay(),providers=providers());assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events)
            assert not a.ctx.alive('ruin') and a.ctx.spatial.blocked_by('enemy') is None and a.ctx.state()['kills']==0
            hits=[thaw(e) for e in a.session.events if e['type']=='damage.accepted' and e['payload']['target']==a.session.world.resolve('ruin')];assert len(hits)==1 and hits[0]['payload']['amount']==100
            result['cases'].append({'name':name,'old100_alive_blocked_counter':True,'actual_hit':hits[0],'CPP_head_full_equal':True,'checkpoint_digest':digest(a.checkpoint()),'kills':0})
        result.update(passed=True,actual_exit=0,whole_stage=False,client_verified=False)
    except Exception as error:result.update(actual_exit=1,error=str(error),traceback=traceback.format_exc())
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':result['passed'],'error':result.get('error')}));return result['actual_exit']


if __name__=='__main__':raise SystemExit(main())
