"""Short identical-model atomic cost comparison; not model acceptance evidence."""
import argparse,json,statistics,sys,time
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();sys.path.insert(0,str(args.runtime.resolve()))
from ark_sim import Compiler,Engine
from ark_sim.kernel import Session
from ark_sim.adapters.api import implementation_digest

def measure(s,iterations=300):
    before=s.checkpoint();samples=[]
    for repeat in range(3):
        begin=time.perf_counter()
        for i in range(iterations):
            with s.atomic():pass
        samples.append(time.perf_counter()-begin)
    assert s.checkpoint()==before
    return {'iterations':iterations,'repeats':3,'seconds':samples,'median_seconds':statistics.median(samples),'kernel_checkpoint_unchanged':True}
s=Session()
for i in range(100):s.world.create('unit',{'value':1},alias='u'+str(i))
for i in range(300):s.schedule('pending',{'value':i},100000)
s.random.sample('a');s.random.sample('b');results={'kernel_no_participant':measure(s)}
for owners in (1,100):
    data={'schemaVersion':2,'entities':[{'id':'peer/unit','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':13,'def':20,'magic_resistance':50}},'resources':{'hp':{'initial':100,'capacity_attribute':'max_hp','role':'health'}},'spatial':{}}}],'scenarioDraft':{'id':'peer/bench','ruleset':'ruleset/ark_standard','map':{'rows':10,'cols':10},'initialEntities':[{'definition':'peer/unit','instanceAlias':'u'+str(i),'position':{'row':i//10,'col':i%10}} for i in range(100)]}}
    sim=Engine.create(Compiler().compile(data))
    for i in range(owners):sim.ctx.attributes.values('u'+str(i))
    for i in range(300):sim.session.schedule('pending',{'value':i},100000)
    sim.session.random.sample('a');sim.session.random.sample('b')
    result=measure(sim.session);result['live_cached_requests']=len(sim.checkpoint()['attribute_cache']['entries']);results['simulation_cached_owners_'+str(owners)]=result
report={'core':implementation_digest(),'scope':'short 100 entities/300 pending tasks/2 RNG streams; empty successful atomics; no whole stage or fidelity claim','results':results};args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
