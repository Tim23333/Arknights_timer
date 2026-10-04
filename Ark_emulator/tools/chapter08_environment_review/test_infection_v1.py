"""Independent source field arithmetic, eligibility and offcell ownership."""
import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter08_environment.policies_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'packages/campaign/chapter08_consumers/environment/infection.module.v3.json'

def package(side=0,motion=1,category=1,free=False,camo=False):
    m=json.loads(MODULE.read_bytes());profile=m['manifest']['metadata']['tile_profile'];p={
        'schemaVersion':2,'manifest':{'id':'package/peer/ch8/infection','requires':['preset/ark_standard']},
        'entities':[{'id':'unit/peer/actor','kind':'entity','tags':['player'] if side==0 else ['enemy'],
            'components':{'attributes':{'base':{'max_hp':70000,'atk':246,'def':1111,'mres':83,'attack_speed_ratio':1.2}},
                'resources':{'hp':{'initial':70000,'capacity':70000,'role':'health'}},'spatial':{},
                'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':1,'target_free':free,'camouflage':camo},
                'lifecycle':{'policy':'policy/ark_lifecycle'}}},
            {'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/leave','ability/peer/back']}}],
        'abilities':[{'id':'ability/peer/leave','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':2,'position':{'row':0,'col':2}}]},'timeline':[]},
            {'id':'ability/peer/back','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':2,'position':{'row':0,'col':1}}]},'timeline':[]}],
        'scenarioDraft':{'id':'scene/peer/ch8/infection','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3,
            'tiles':[{'tileKey':'tile_floor','buildableType':1,'passableMask':3},
                {'tileKey':'tile_infection','buildableType':0,'passableMask':3,'blackboard':profile['expected_blackboard'],'effects':None},
                {'tileKey':'tile_floor','buildableType':1,'passableMask':3}], 'tile_mechanics':{'tile_infection':profile}},
            'initialEntities':[{'definition':'unit/peer/actor','instanceAlias':'actor','position':{'row':0,'col':1}},
                {'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':0}}]}}
    return p

def make(p):
    reg=providers();program=Compiler(providers=reg).compile(p,packages=[str(MODULE)]);return Engine.create(program,providers=reg),reg

def test_independent_300s299packets_deathfree_offtile_CP_head(tmp_path):
    p=package();s,reg=make(p);s.submit({'action':'skill','source':'director','ability':'ability/peer/leave'},at=35)
    s.submit({'action':'skill','source':'director','ability':'ability/peer/back'},at=65)
    s.submit({'action':'skill','source':'director','ability':'ability/peer/leave'},at=95)
    s.advance(100);cp=tmp_path/'source100.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h),providers=reg)
    s.advance(8901);r.advance(8901);head=replay(s.program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==299
    assert hits[0]['time']==30 and hits[-1]['time']==8970 and all(e['payload']['amount']==180 and e['payload']['source'] is None for e in hits)
    assert s.ctx.resources.current('actor','hp')==16180
    assert s.ctx.attributes.value('actor','atk')==246 and s.ctx.attributes.value('actor','attack_speed_ratio')==1.2
    assert not any(i['definition']=='buff/ch8/environment/tile_infection' for i in s.ctx.get('actor',('buffs','instances'),[]))

@pytest.mark.parametrize('side',[0,1,2])
def test_ground_allside_targetfree_camouflage_are_not_exempt(side):
    s,_=make(package(side=side,free=True,camo=True));s.advance(31)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['payload']['amount']==180
    assert s.ctx.attributes.value('actor','atk')==369 and s.ctx.attributes.value('actor','attack_speed_ratio')==1.7

@pytest.mark.parametrize('motion,category',[(2,1),(1,2),(1,4)])
def test_source_ground_category_charonly_rejects(motion,category):
    s,_=make(package(motion=motion,category=category));s.advance(31)
    assert not [e for e in s.session.events if e['type']=='damage.accepted']
    assert s.ctx.resources.current('actor','hp')==70000
