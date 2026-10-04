import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]


def fixture(key):
    p=json.loads((ROOT/'packages/campaign/chapter05_units/ordinary.reference_model.json').read_bytes())
    unit=next(e['id'] for e in p['entities'] if key in e['id'])
    guard={'id':'unit/root_guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':80,'def':31,'mres':0,'block_count':3}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'deployable':{'cost':0,'terrain':1},
        'abilities':['ability/root_hurt'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p['entities'].append(guard);p['abilities'].append({'id':'ability/root_hurt','kind':'ability','activation':{'mode':'manual'},
        'timeline':[{'at':0,'effect':{'op':'damage','target':2,'damage_type':'true','scale':1}}]})
    p['scenarioDraft']={'id':'scene/root_ordinary/'+key,'ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':5},
        'resources':{'dp':{'initial':25,'capacity':99}},'initialEntities':[{'definition':unit,'instanceAlias':'enemy','position':{'row':0,'col':0},
            'route':{'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}},
            {'definition':'unit/root_guard','instanceAlias':'guard','position':{'row':0,'col':1},'deployed':True}]}
    return p


@pytest.mark.parametrize('key,hp,atk,frame,interval',[('lunsbr',3200,350,12,60),('wteeth',5000,500,19,90)])
def test_exact_damage_relative_frame_no_regen_and_public_withdraw_releases_target(key,hp,atk,frame,interval):
    p=fixture(key);s=Engine.create(Compiler().compile(p),seed=505)
    s.submit({'action':'skill','source':'guard','ability':'ability/root_hurt'},at=2)
    s.submit({'action':'withdraw','source':'guard'},at=interval+40)
    s.advance(frame);r=Engine.restore(s.program,s.checkpoint());s.advance(interval+50);r.advance(interval+50)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==2]
    casts=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==2]
    assert len(hits)==2 and [e['payload']['amount'] for e in hits]==[atk-31]*2
    assert all(h['time']-c['time']==frame for h,c in zip(hits,casts))
    assert hits[1]['time']-hits[0]['time']==interval
    assert s.ctx.resources.current('enemy','hp')==hp-80
    assert not s.ctx.active('guard') and s.ctx.spatial.blocked_by('enemy') is None


@pytest.mark.parametrize('key,hp',[('lunsbr',3200),('wteeth',5000)])
def test_death_has_single_lifecycle_terminal_and_no_new_attack_or_heal(key,hp):
    p=fixture(key);p['entities'][-1]['components']['attributes']['base']['atk']=hp
    s=Engine.create(Compiler().compile(p),seed=505);s.submit({'action':'skill','source':'guard','ability':'ability/root_hurt'},at=3)
    s.advance(100)
    assert s.ctx.resources.current('enemy','hp')==0 and not s.ctx.alive('enemy')
    assert len([e for e in s.session.events if e['type']=='entity.died' and e['payload']['target']==2])==1
    assert not [e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['source']==2]
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
