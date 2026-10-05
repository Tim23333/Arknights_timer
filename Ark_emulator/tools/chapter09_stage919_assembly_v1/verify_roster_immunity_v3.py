"""Actual roster Buff definitions respect native boss immunity in the stage."""
import argparse,json,os,sys,traceback
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    from ark_sim import Compiler,Engine
    from ark_sim.tools.replay import replay
    from ark_sim.contracts import digest
    from tools.chapter09_stage919_assembly_v1.providers_v3 import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    result={'passed':False,'cases':[]}
    try:
        stage=json.loads((ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v3.life99999.json').read_bytes())
        for buff in ('buff/campaign_chen_stun','buff/support_mon3tr_death_stun','buff/ch9/pillar/stun10'):
            p=deepcopy(stage);ability='ability/919/fixture/apply_stun'
            chen=next(d for d in p['definitions'] if d['id']=='unit/char_010_chen');chen['components']['abilities'].append(ability)
            chen['components'].pop('behavior',None)
            p['definitions'].append({'id':ability,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/919/fixture/boss','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':buff}}]})
            p['definitions'].append({'id':'selector/919/fixture/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'},{'state':'alive'}],'limit':1})
            boss=next(d for d in p['definitions'] if d['id']=='unit/ch9/mandra/body');boss['components'].pop('behavior',None)
            p['scenarioDraft']={'id':'scene/919/immunity/'+buff.split('/')[-1],'ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':3},'initialEntities':[{'definition':chen['id'],'instanceAlias':'source','position':{'row':1,'col':0}},{'definition':boss['id'],'instanceAlias':'boss','position':{'row':1,'col':1}}],'commands':[{'at':5,'action':'skill','source':'source','ability':ability}]}
            program=Compiler(providers=providers()).compile(p);a=Engine.create(program,providers=providers());a.advance(4);q=Path(os.environ['ARKSIM_RUN_DIR'])/(buff.split('/')[-1]+'.checkpoint.json');pin=write_ordered(q,a.checkpoint());b=Engine.restore(program,load_bound(q,pin),providers=providers());a.advance(6);b.advance(6);h=replay(program,a.export_replay(),providers=providers());assert a.checkpoint()==b.checkpoint()==h.checkpoint()
            assert all(a.ctx.buffs.controls('boss').values())
            instances=a.ctx.get('boss',('buffs','instances'));actual=next(i for i in instances if i['definition']==buff);assert actual['applicability']['control'] is False
            assert a.ctx.resources.current('boss','hp')==50000
            result['cases'].append({'buff':buff,'actual_source_definition':chen['id'],'actual_command_at':5,'held_buff_control_suppressed':True,'actual_controls':a.ctx.buffs.controls('boss'),'CPP_head_full_equal':True,'checkpoint_digest':digest(a.checkpoint())})
        result.update(passed=True,actual_exit=0,whole_stage=False)
    except Exception as error:result.update(actual_exit=1,error=str(error),traceback=traceback.format_exc())
    args.output.parent.mkdir(parents=True,exist_ok=True);assert not args.output.exists();args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':result['passed'],'error':result.get('error')}));return result['actual_exit']


if __name__=='__main__':raise SystemExit(main())
