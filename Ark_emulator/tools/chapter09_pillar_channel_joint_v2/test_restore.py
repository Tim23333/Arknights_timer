import sys,json,copy,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_pillar_channel_joint_v2_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_depletion import test_depletion_v2 as primitive
OUT=ROOT/'validation/campaign/chapter09_pillar_channel_joint_v2'
def baseline():
    d=primitive.data();d['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'source','ability':'ability/depletion/hit'}]
    s=Engine.create(Compiler(providers=primitive.registry()).compile(d),providers=primitive.registry(),seed=773);s.session.advance(8);cp=primitive.cp(s)
    assert cp['attribute_cache']['entries']==[], 'Counter requires natural empty cache, not artificial deletion'
    return s,cp
def state(cp):return next(e for e in cp['kernel']['world']['entities'] if e['definition_id']=='unit/depletion/target')['components']['runtime']['depletion']
def reject(s,cp):
    try:Engine.restore(s.program,cp,providers=primitive.registry())
    except ValueError as error:return str(error)
    raise AssertionError('Tampered missing finite owner restored')
def main():
    before=implementation_digest();results=[];errors={}
    for case in ['missing_lease','generation_zero_normal_no_lease','orphan_extra_task','coherent_wrong_generation','legitimate_withdraw_finish_dead']:
        try:
            s,cp=baseline();changed=copy.deepcopy(cp)
            if case=='missing_lease':state(changed)['lease']=None;errors[case]=reject(s,changed)
            elif case=='generation_zero_normal_no_lease':state(changed).update(generation=0,stage='normal',lease=None);errors[case]=reject(s,changed)
            elif case=='orphan_extra_task':
                task=next(t for t in changed['kernel']['scheduler']['tasks'] if t['kind']=='domain.depletion.action');extra=copy.deepcopy(task);extra['id']=changed['kernel']['scheduler']['next_id'];changed['kernel']['scheduler']['next_id']+=1;extra['seq']=changed['kernel']['scheduler']['next_seq'];changed['kernel']['scheduler']['next_seq']+=1;changed['kernel']['scheduler']['tasks'].append(extra);errors[case]=reject(s,changed)
            elif case=='coherent_wrong_generation':
                st=state(changed);st['generation']=5;lease=st['lease'];lease['generation']=5;changed['kernel']['events']['records'][lease['started_event']-1]['payload']['generation']=5
                for row in lease['actions'].values():
                    changed['kernel']['events']['records'][row['issued_event']-1]['payload']['generation']=5
                    if row['executed_event']:changed['kernel']['events']['records'][row['executed_event']-1]['payload']['generation']=5
                for t in changed['kernel']['scheduler']['tasks']:
                    if t['kind']=='domain.depletion.action':t['payload']['generation']=5
                errors[case]=reject(s,changed)
            else:
                s.ctx.lifecycle.retire('target','withdrawn');r=Engine.restore(s.program,primitive.cp(s),providers=primitive.registry());s.session.advance(100);r.session.advance(100);assert primitive.cp(s)==primitive.cp(r)
                d=primitive.data();d['rules'][0]['implementation']={'type':'expression','expression':"{'action':'finish','stage':inputs.state.stage,'actions':[]}"};p=Compiler(providers=primitive.registry()).compile(d);s=Engine.create(p,providers=primitive.registry());primitive.zero(s);assert not s.ctx.alive('target');r=Engine.restore(p,primitive.cp(s),providers=primitive.registry());assert primitive.cp(r)==primitive.cp(s)
            results.append({'case':case,'passed':True})
        except Exception as error:results.append({'case':case,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    report={'core_before':before,'core_after':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'rejections':errors,'counter_method':'Public damage at7, checkpoint at8 with natural attribute_cache.entries==[]; no cache edits'};(OUT/'author.restore.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
