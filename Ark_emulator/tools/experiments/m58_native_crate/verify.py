"""Fresh exact source-crate and primary projectile consumer under M58."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
CORE='1ef9635ee70a8159e0523156aeeb177329d19d12a26185b98b9d9fa55ea3c3d5'
PACKAGE=ROOT/'packages/campaign/chapter03_stage_models/level_main_03-07.m58.reference_model.json'
CRATE=ROOT/'packages/campaign/chapter03_traps/crate.reference_v2.partial.json'
OUT=ROOT/'validation/campaign/m58_native_crate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations,export_events,write_canonical


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    assert hashlib.sha256(PACKAGE.read_bytes()).hexdigest()=='4195745d994c01503e1666b4f1caec036b1efda71b4030284bd95b74280c5c06'
    assert hashlib.sha256(CRATE.read_bytes()).hexdigest()=='eeee6f654c0c2344743a396bd46d0cfa941a891bd27838ad81f3eace0fbec7cc'
    guards=[PACKAGE,CRATE,Path(__file__)];before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    p=json.loads(PACKAGE.read_bytes());crate=json.loads(CRATE.read_bytes())
    replacements={d['id']:d for d in crate['entities']+crate['rules']}
    p['definitions']=[replacements.pop(d['id'],d) for d in p['definitions']]+list(replacements.values())
    p['definitions'].append({'id':'unit/peer_air','kind':'entity','tags':['player'],'components':{
        'spatial':{'motion_mode':1},'selection_state':{'side':0,'motion':2,'category':1},'attributes':{'base':{'max_hp':2000,'def':73,'mres':0}},
        'resources':{'hp':{'initial':2000,'capacity':2000,'role':'health'}}}})
    p['definitions'].extend([{'id':'unit/peer_director','kind':'entity','components':{'spatial':{},'selection_state':{'side':2,'motion':0,'category':0},'abilities':['ability/peer_air']}},
        {'id':'ability/peer_air','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'spawn','definition':'unit/peer_air','position':{'row':0,'col':2}}]},'timeline':[]}])
    stage_rules=p['scenarioDraft']['rules']
    p['scenarioDraft']={'id':'scene/m58/native_crate_cross','ruleset':'ruleset/ark_standard','rules':stage_rules,'objectives':{'type':'waves','life_resource':'life'},
        'map':{'rows':1,'cols':4},'roster':['unit/ch3/crate'],'resources':{'dp':{'initial':10,'capacity':99},'life':{'initial':99999,'capacity':99999},'crate_cards':{'initial':5,'capacity':5}},
        'initialEntities':[{'definition':'unit/peer_director','instanceAlias':'director','position':{'row':0,'col':3}}],
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':.1,'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/ch3/mortar','instanceAlias':'mortar','position':{'row':0,'col':0},
            'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}}]}]}]}}
    commands=[{'at':0,'action':'deploy','definition':'unit/ch3/crate','alias':'crate','position':{'row':0,'col':1}},
              {'at':220,'action':'deploy','definition':'unit/ch3/crate','alias':'crate2','position':{'row':0,'col':3}},
              {'at':30,'action':'skill','source':'director','ability':'ability/peer_air'}]
    program=Compiler().compile(p);s=Engine.create(program,seed=58079)
    for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
    s.advance(40);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.advance(35);r.advance(35)
    first=[e for e in s.session.events if e['type']=='damage.accepted']
    air=next(e['id'] for e in s.session.world.entities() if e['definition_id']=='unit/peer_air')
    if len(first)!=2:
        print(json.dumps(thaw({'tick':s.session.time,'packets':[(e['time'],e['payload']) for e in first],
             'position':s.ctx.get('mortar',('spatial','position')),'blocked':s.ctx.spatial.blocked_by('mortar'),
             'launches':[(e['time'],e['payload']) for e in s.session.events if e['type']=='projectile.launched']})))
    assert [(e['payload']['target'],e['payload']['amount']) for e in first]==[(s.session.world.resolve('crate'),100),(air,327)]
    assert [e['time'] for e in first]==[65,65]
    assert s.ctx.resources.current('system/battle','crate_cards')==4
    assert s.ctx.resources.current('system/battle','dp')==5
    s.advance(325);r.advance(325)
    assert s.ctx.state()['finished'] and s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','life')==99998
    assert not s.ctx.alive('crate') and not s.ctx.alive('crate2') and not s.ctx.state()['terrain']['layers']
    observed=observations(s);assert observed==observations(r)==observations(replay(program,s.export_replay()))
    for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(OUT/name,value)
    journal=export_events(OUT/'events.jsonl',s);after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};assert before==after and implementation_digest()==CORE
    write_canonical(OUT/'reference_fee_weight_partial_review.json',{'schema':'ark-sim/native-crate-primary-integrated-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'source_start':before,'source_end':after,
        'actual_first_packets':[(e['time'],e['payload']['amount']) for e in first],'expected_first_packets':[100,327],'end_tick':400,'observations':observed,'journal':journal,
        'durable_checkpoint_equal':True,'replay_equal':True,'checkpoint_sha256':pin,'whole_stage_executed':False,'actual_client_verified':False,
        'required_gaps':crate['manifest']['metadata']['model_gaps'],
        'scope':'Corrected constantfee and1000weight partial derivative; actual radius/HP/cards/category4 plus primary original10s projectile, two public cards at0/220, destruction/path continue/leak, DEF73 aerial splash. This one-corridor stress intentionally does not claim missing forbid-seal/cooldown-start policies.'})
    print(json.dumps({'passed':True,'end_tick':400,'events':observed['event_count']}))


if __name__=='__main__':main()
