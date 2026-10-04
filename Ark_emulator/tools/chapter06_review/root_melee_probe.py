"""Fresh public deployments and exact source hits on a separate DEF37 blocker."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v8_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    core=implementation_digest();assert core=='13c8f6f856ea622d35604cc88cd4122b0dc6e5f985be4eedfba46699d2b8c42b'
    source=ROOT/'packages/campaign/chapter06_units/melee.model.json';cold=ROOT/'packages/campaign/chapter06_cold/model.json'
    assert sha(source)=='7417d5342a7affec7d872715bb810c01dc65422dcd30c41064d33ec33a776f31'
    out=ROOT/'validation/campaign/root_chapter06_melee_v1';assert not out.exists();out.mkdir(parents=True)
    results=[]
    for native,atk,hits in [('enemy_1006_shield_2',600,[15,93]),('enemy_1064_snsbr',360,[13,73])]:
        p=json.loads(source.read_bytes());enemy=next(d for d in p['entities'] if d['metadata']['native_reference']['id']==native)
        p['entities'].append({'id':'unit/root/def37','kind':'entity','tags':['player','ground'],'components':{
            'attributes':{'base':{'max_hp':9000,'atk':0,'def':37,'mres':0,'block_count':1}},
            'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'spatial':{},
            'deployable':{'base_cost':7,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
        p['scenarioDraft']={'id':'scene/root/'+native,'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},'objectives':{},
            'resources':{'dp':{'initial':20,'capacity':99}},'roster':['unit/root/def37'],
            'initialEntities':[{'definition':enemy['id'],'instanceAlias':'enemy','position':{'row':0,'col':0},
                'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}}]}
        reg=providers();program=Compiler(providers=reg).compile(p,packages=[cold]);sim=Engine.create(program,seed=662,providers=reg)
        sim.submit({'action':'deploy','definition':'unit/root/def37','alias':'guard','position':{'row':0,'col':0}},at=0)
        sim.session.advance(2)
        assert sim.ctx.resources.current('system/battle','dp')==13
        assert sim.ctx.get('enemy',('runtime','blocked_by'))==sim.session.world.resolve('guard')
        cp=out/(native+'.checkpoint.json');pin=write_ordered(cp,sim.checkpoint());restore=Engine.restore(program,load_bound(cp,pin),providers=reg)
        until=hits[-1]+2
        sim.session.advance(until-2);restore.session.advance(until-2)
        events=[e for e in sim.session.events if e['type']=='damage.accepted' and e['payload']['source']==sim.session.world.resolve('enemy')]
        assert [e['time'] for e in events]==hits
        assert [e['payload']['amount'] for e in events]==[atk-37,atk-37]
        assert sim.ctx.resources.current('guard','hp')==9000-2*(atk-37)
        head=replay(program,sim.export_replay(),providers=reg);assert sim.checkpoint()==restore.checkpoint()==head.checkpoint()
        results.append({'native':native,'passed':True,'accepted_hits':hits,'amounts':[e['payload']['amount'] for e in events],
                        'durable_checkpoint_sha':pin,'head_equal':True,'event_count':len(sim.session.events)})
    assert core==implementation_digest()
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump({'passed':True,'core':core,'module_sha':sha(source),'results':results,
        'helper_sha':sha(Path(__file__)),'scope':'Root separate DEF37 public block/attack/CP/head probe; source Frozen branch separately reviewed, no whole-stage approval'},f,indent=2)
    print(json.dumps({'passed':True,'cases':len(results),'sha':sha(target)}))


if __name__=='__main__':main()
