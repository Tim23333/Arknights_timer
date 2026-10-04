import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]


def fixture():
    p=json.loads((ROOT/'packages/campaign/chapter05_boss/faust/combat.v3.reference.json').read_bytes())
    hero={'id':'unit/hero','kind':'entity','tags':['player'],'components':{'attributes':{'base':{
        'max_hp':100000,'atk':100,'def':37,'block_count':3}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'deployable':{'cost':0,'terrain':1},
        'abilities':['ability/strike'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p['entities'].append(hero);p['abilities'].append({'id':'ability/strike','kind':'ability','activation':{'mode':'manual'},
        'timeline':[{'at':0,'effect':{'op':'damage','target':2,'damage_type':'true','scale':1}}]})
    p['scenarioDraft']={'id':'scene/faust','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':8},
        'resources':{'dp':{'initial':10,'capacity':99}},'rules':p['manifest']['metadata']['stage_rules'],
        'initialEntities':[{'definition':'unit/ch5/faust/level0','instanceAlias':'boss','position':{'row':0,'col':1}},
            {'definition':'unit/hero','instanceAlias':'hero','position':{'row':0,'col':2}}]}
    return p


def create(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=51005)


def test_real_normal_frame40_plus3flight_then_sharedcritical600():
    s=create();s.advance(42);r=Engine.restore(s.program,s.checkpoint());s.advance(603);r.advance(603)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    damage=[(e['time'],e['payload']['amount'],e['payload']['ability']) for e in s.session.events if e['type']=='damage.accepted']
    assert damage[:4]==[(43+150*i,963,'ability/ch5/faust/normal') for i in range(4)]
    assert damage[-1]==(643,1963,'ability/ch5/faust/critical')
    assert s.ctx.resources.current('boss','hp')==37000


def test_source_invincible_expiry_exact4500_does_not_extend_into_next_tick():
    p=fixture();p['entities'][0]['components']['abilities']=[];p['entities'][0]['components'].pop('ability_arbitration');p['entities'][0]['components'].pop('behavior')
    s=create(p)
    s.submit({'action':'skill','source':'hero','ability':'ability/strike'},at=4499)
    s.submit({'action':'skill','source':'hero','ability':'ability/strike'},at=4500)
    s.advance(4498);r=Engine.restore(s.program,s.checkpoint());s.advance(3);r.advance(3)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert s.ctx.resources.current('boss','hp')==36900
    assert not s.ctx.get('boss',('buffs','instances'))


def test_source_blockfree_passes_real_deployed_ground_blocker():
    p=fixture();p['entities'][0]['components']['abilities']=[];p['entities'][0]['components'].pop('ability_arbitration');p['entities'][0]['components'].pop('behavior')
    item=p['scenarioDraft']['initialEntities'][0]
    item['position']={'row':0,'col':0};item['route']={'motionMode':0,'startPosition':{'row':0,'col':0},
        'endPosition':{'row':0,'col':7},'checkpoints':[]}
    p['scenarioDraft']['initialEntities'].pop()
    s=create(p);s.submit({'action':'deploy','entity':'unit/hero','alias':'guard','position':{'row':0,'col':1}},at=0);s.advance(100)
    assert s.ctx.get('boss',('runtime','blocked_by')) is None
    assert s.ctx.get('boss',('spatial','position','col'))>1


def test_advancedselector_ground_motion_excludes_air_even_higher_taunt():
    p=fixture();air=deepcopy(p['scenarioDraft']['initialEntities'][1]);air['instanceAlias']='air'
    air['components']={'selection_state':{'motion':2},'spatial':{'motion_mode':1},'attributes':{'base':{'taunt_level':999}}}
    p['scenarioDraft']['initialEntities'].append(air)
    s=create(p);s.advance(44)
    assert s.ctx.resources.current('air','hp')==100000 and s.ctx.resources.current('hero','hp')==99037
