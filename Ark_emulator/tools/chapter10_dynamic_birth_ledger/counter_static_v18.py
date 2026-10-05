"""A real declared child spawn exposes V18's static-wave-only birth check."""
import json,os,sys,traceback
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw,digest
from ark_sim.adapters.api import implementation_digest


def main():
    def entity(name,hp,tags,abilities=()):
        return {'id':'unit/ledger/'+name,'kind':'entity','tags':tags,'components':{
            'attributes':{'base':{'max_hp':hp,'atk':10000,'def':0,'mres':0}},
            'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'spatial':{},
            'abilities':list(abilities),'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    parent='unit/ledger/parent';child='unit/ledger/child';operator='unit/ledger/operator'
    p={'schemaVersion':2,'entities':[entity('parent',4500,['enemy']),entity('child',1500,['enemy']),
         entity('operator',5000,['player'],['ability/ledger/first','ability/ledger/second'])],
       'selectors':[{'id':'selector/ledger/parent','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['definition_id'],'equals':parent}},{'state':'alive'}],'limit':1},
                    {'id':'selector/ledger/child','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['definition_id'],'equals':child}},{'state':'alive'}],'limit':1}],
       'abilities':[{'id':'ability/ledger/first','kind':'ability','activation':{'mode':'manual'},'selector':'selector/ledger/parent',
                     'timeline':[{'at':0,'effects':[{'op':'damage','damage_type':'true','scale':1},{'op':'spawn','definition':child,'owner':'source'}]}]},
                    {'id':'ability/ledger/second','kind':'ability','activation':{'mode':'manual'},'selector':'selector/ledger/child','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}],
       'scenarioDraft':{'id':'scene/ledger/actual','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':3},
        'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},
        'initialEntities':[{'definition':operator,'instanceAlias':'operator','position':{'row':1,'col':1}}],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':parent,'instanceAlias':'parent','position':{'row':0,'col':1}},'count':1,'managed':True,'blocks_wave':True}]}]}]},
        'commands':[{'at':5,'action':'skill','source':'operator','ability':'ability/ledger/first'},
                    {'at':8,'action':'skill','source':'operator','ability':'ability/ledger/second'}]}}
    result={'passed':False,'actual_exit':1,'scope':'Declared spawn/ledger counter only; does not implement native death-route inheritance'}
    try:
        program=Compiler().compile(p);a=Engine.create(program);a.advance(6)
        q=Path(os.environ['ARKSIM_RUN_DIR'])/'actual.checkpoint.json';q.write_text(json.dumps(a.checkpoint()),encoding='utf8')
        b=Engine.restore(program,json.loads(q.read_bytes()));a.advance(4);b.advance(4);h=replay(program,a.export_replay());assert a.checkpoint()==b.checkpoint()==h.checkpoint()
        state=a.ctx.state();assert state['finished'] and state['kills']==2 and state['leaks']==0
        expected=Counter({parent:1});actual=Counter(e['definition_id'] for e in a.session.world.entities() if 'enemy' in e['tags'])
        assert actual==Counter({parent:1,child:1}) and expected!=actual
        result.update(passed=True,actual_exit=0,core=implementation_digest(),native_wave_expectation=dict(expected),
            actual_observed_births=dict(actual),finished=True,kills=2,leaks=0,
            static_v18_birth_equality_rejects_valid_declared_spawn=True,CPP_head_full_equal=True,
            checkpoint_digest=digest(a.checkpoint()),actual_creation_events=[thaw(e) for e in a.session.events if e['type']=='entity.created'],
            requirement='New owned spawn lineage and pending-birth ledger must authenticate declared descendants; do not filter actors or overwrite counters.')
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    out=ROOT/'validation/campaign/chapter10_dynamic_birth_ledger/static.v18.counter.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':result['passed'],'error':result.get('error')}));return result['actual_exit']


if __name__=='__main__':raise SystemExit(main())
