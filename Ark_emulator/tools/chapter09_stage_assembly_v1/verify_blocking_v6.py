"""Observe actual selected blocking rule and exact squared-radius boundaries."""
import argparse,json,math,os,sys,traceback
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.contracts import thaw,digest
    from ark_sim.tools.replay import replay
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter09_stage_assembly_v1.providers_v6 import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    core='2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0';assert implementation_digest()==core
    result={'core':core,'passed':False,'cases':[]};base=ROOT/'packages/campaign/chapter09_stage_models'
    def fixture(version,epsilon):
        p=json.loads((base/f'level_main_09-16.native_draft.v{version}.life99999.json').read_bytes());unit=next(d for d in p['definitions'] if d['kind']=='entity' and d['id'].startswith('unit/ch9/duhond/'));unit['components'].pop('behavior');unit['components']['abilities']=[];unit['components']['attributes']['base']['move_speed']=0
        radius=math.sqrt(.30000001192092896);dc=.49;dr=math.sqrt((radius+epsilon)**2-dc**2);pos={'row':2+dr,'col':2+dc};route={'startPosition':pos,'endPosition':{'row':4,'col':2},'motionMode':0,'checkpoints':[]}
        bindings=deepcopy(p['scenarioDraft']['rules']);p['scenarioDraft']={'id':f'scene/block/{version}/{epsilon}','ruleset':'ruleset/ark_standard','rules':bindings,'map':{'rows':5,'cols':5},'objectives':{},'initialEntities':[{'definition':'unit/ch9/pillar/ruin','instanceAlias':'ruin','position':{'row':2,'col':2}},{'definition':unit['id'],'instanceAlias':'enemy','position':pos,'route':route}]};return p
    try:
        for version,epsilon,want in [(5,.0001,True),(6,-.0001,True),(6,.0001,False)]:
            p=fixture(version,epsilon);program=Compiler(providers=providers()).compile(p);a=Engine.create(program,providers=providers());a.advance(1)
            selected=[thaw(e) for e in a.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='blocking.eligibility']
            actual=a.ctx.spatial.blocked_by('enemy') is not None
            fact={'version':version,'epsilon':epsilon,'expected':want,'actual':actual,'position':a.ctx.get('enemy',('spatial','position')),'path':a.ctx.get('enemy',('spatial','movement_path')),'selected_rules':sorted({e['payload']['rule_id'] for e in selected})};result['cases'].append(fact)
            assert actual==want
            assert ('rule/ch9/scenario_blocking' if version==6 else 'rule/ark_block_eligibility') in fact['selected_rules']
            q=Path(os.environ['ARKSIM_RUN_DIR'])/f'v{version}_{epsilon}.checkpoint.json';pin=write_ordered(q,a.checkpoint());b=Engine.restore(program,load_bound(q,pin),providers=providers());a.advance(1);b.advance(1);h=replay(program,a.export_replay(),providers=providers());assert a.checkpoint()==b.checkpoint()==h.checkpoint();fact.update(CPP_head_full_equal=True,checkpoint_digest=digest(a.checkpoint()))
        result.update(passed=True,actual_exit=0,whole_stage=False)
    except Exception as error:result.update(actual_exit=1,error=str(error),traceback=traceback.format_exc())
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':result['passed'],'error':result.get('error')}));return result['actual_exit']


if __name__=='__main__':raise SystemExit(main())
