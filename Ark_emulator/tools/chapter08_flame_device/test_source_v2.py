"""Real25sSP neutraldevice4rays, currentRES and postretireburn CP/head."""
import json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_buff_lifetime_v4_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_flame_device.build_module_v2 import OUT,UNIT,build,sha
from tools.chapter08_flame_device.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def package():
    assert sha(OUT)=='ddb9686b18d559f9545592ebf55d016a6a3e3c46d922e6ba7f8ef51e480ae894'
    p=json.loads(OUT.read_bytes());p['entities'].append({'id':'unit/flame/target','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'max_hp':10000,'atk':0,'def':813,'mres':27,'one_minus_status_resistance':1}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']={'id':'scene/flame/source','ruleset':'ruleset/ark_standard','seed':81710,'map':{'rows':5,'cols':5},
        'initialEntities':[{'definition':UNIT,'instanceAlias':'flame','position':{'row':2,'col':2}},
            *[{'definition':'unit/flame/target','instanceAlias':'target/'+str(i),'position':v} for i,v in enumerate([{'row':1,'col':2},{'row':2,'col':3},{'row':3,'col':2},{'row':2,'col':1}])]]}
    return p

def test_exactsource_rebuild_SP25_and4retained1000arts_rays_burn_aftercast_retire(tmp_path):
    assert json.loads(OUT.read_bytes())==build();p=package();reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    s.advance(740);cp=tmp_path/'device740.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(60);r.advance(60);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==4 and len({e['payload']['definition'] for e in launches})==4
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==8
    fixed=[e for e in hits if e['payload']['amount']==730];assert len(fixed)==4
    assert not s.ctx.active('flame') and s.ctx.resources.current('flame','hp')==6000
    assert [s.ctx.resources.current('target/'+str(i),'hp') for i in range(4)]==[9214]*4

def test_device_dies_beforeSPfull_no_rays_terrain_restored():
    p=package();p['entities'][-1]['components']['abilities']=['ability/kill_device'];p['entities'][-1]['components']['attributes']['base']['atk']=6000
    p['selectors']=[{'id':'selector/flame','kind':'selector','region':{'type':'all'},'filters':[{'tag':'flame'}]}]
    p['abilities'].append({'id':'ability/kill_device','kind':'ability','selector':'selector/flame','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);s.submit({'action':'skill','source':'target/0','ability':'ability/kill_device'},at=600);s.advance(800)
    assert not [e for e in s.session.events if e['type']=='projectile.launched']
    assert s.ctx.resources.current('flame','hp')==0
