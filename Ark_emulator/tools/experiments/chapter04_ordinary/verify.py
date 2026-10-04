"""Source-operand checks for newly authored chapter4 ordinary melee actors."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate'
CORE='e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'
MODEL=ROOT/'packages/campaign/chapter04_units/ordinary.reference_model.json'
SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json'
OUT=ROOT/'validation/campaign/chapter04_ordinary'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations,export_events,write_canonical


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest()=='d53bcd485b0b67bf971fb39176fdb2abfa962e8c9055b6eb07ce643dbeff0038'
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603'
    guards=[MODEL,SOURCE,Path(__file__)];before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    module=json.loads(MODEL.read_bytes());source=json.loads(SOURCE.read_bytes());cases=[]
    for unit in module['entities']:
        variant=source['variants'][unit['metadata']['native_variant_id']];native=variant['modes'][0]['nodes']['_combat'];a=variant['native_enemy']['resolved']['attributes']
        assert not variant.get('additional_animation_drivers') and not variant['passive_and_skill_components']
        p=json.loads(MODEL.read_bytes());p['entities'].append({'id':'unit/guard','kind':'entity','tags':['player'],'components':{'spatial':{},
            'attributes':{'base':{'max_hp':50000,'def':175,'mres':0,'block_count':1}},'resources':{'hp':{'initial':50000,'capacity':50000,'role':'health'}},
            'deployable':{'base_cost':0,'cooldown_seconds':0,'capacity':1,'terrain':'ground'}}})
        p['scenarioDraft']={'id':'scene/c4/sourceordinary','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},
            'roster':['unit/guard'],'resources':{'dp':{'initial':1,'capacity':1}},'initialEntities':[{'definition':unit['id'],'instanceAlias':'enemy','position':{'row':0,'col':0},
                'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}]}
        program=Compiler().compile(p);s=Engine.create(program,seed=4407)
        commands=[{'at':0,'action':'deploy','definition':'unit/guard','alias':'guard','position':{'row':0,'col':0}}]
        s.submit({k:v for k,v in commands[0].items() if k!='at'},at=0);s.advance(2)
        assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard')
        frames=[e['frame'] for e in native['animation_binding']['events'] if e['name']=='OnAttack'];damage=a['atk']/(2 if native['native_class']=='MultiMeleeAttack' else 1)
        directory=OUT/variant['native_reference']['id'];directory.mkdir(parents=True,exist_ok=True);cp=directory/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin))
        end=max(frames)+2;s.advance(end-2);r.advance(end-2);actual=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted'];expected=[(f+1,max(damage-175,damage*.05)) for f in frames]
        assert actual==expected,(actual,expected);observed=observations(s);assert observed==observations(r)==observations(replay(program,s.export_replay()))
        for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(directory/name,value)
        journal=export_events(directory/'events.jsonl',s);cases.append({'variant':variant['variant_id'],'source_frames':frames,'expected':expected,'actual':actual,'observations':observed,'journal':journal,'durable_checkpoint_equal':True,'replay_equal':True})
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};assert before==after and implementation_digest()==CORE
    write_canonical(OUT/'final_review.json',{'schema':'ark-sim/chapter04-ordinary-model-tests/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'source_start':before,'source_end':after,'cases':cases,
        'scope':'Author source-model assertions; seven actual public deployment block/frame/damage/diskCP/replay cases; independent peer pending','whole_stage_executed':False,'actual_client_verified':False})
    print(json.dumps({'passed':True,'cases':len(cases)}))


if __name__=='__main__':main()
