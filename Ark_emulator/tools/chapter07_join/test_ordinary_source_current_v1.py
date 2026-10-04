"""Fresh unequal-defense and public timing probes for exact current source units."""
import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[2]
CASES=[('sotihd','chapter07_ordinary/sotihd.module.v4.reference.json',2900,350,150,18,42),
       ('sotisd','chapter07_ordinary_remaining/sotisd.module.v3.reference.json',15000,700,1300,28,114)]


def package(rel):
    p=json.loads((ROOT/'packages/campaign'/rel).read_bytes());uid=p['entities'][0]['id']
    p['entities'].append({'id':'unit/peer/current/blocker','kind':'entity','tags':['player','ground'],
        'components':{'attributes':{'base':{'max_hp':10101,'atk':0,'def':137,'mres':17,'block_count':1}},
            'resources':{'hp':{'initial':10101,'capacity':10101,'role':'health'}},
            'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},
            'deployable':{'base_cost':7,'capacity':1,'terrain':'ground','cooldown_seconds':0},
            'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']={'id':'scene/current/source_normal','ruleset':'ruleset/ark_standard',
        'map':{'rows':1,'cols':4},'resources':{'dp':{'initial':20,'capacity':99}},'objectives':{},
        'roster':['unit/peer/current/blocker'],'initialEntities':[{'definition':uid,'instanceAlias':'enemy',
            'position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},
                'endPosition':{'row':0,'col':3},'checkpoints':[]}}]}
    return p


def make(rel):
    s=Engine.create(Compiler().compile(package(rel)),seed=7191)
    s.submit({'action':'deploy','entity':'unit/peer/current/blocker','row':0,'col':0,'alias':'blocker'},at=0)
    return s


@pytest.mark.parametrize('name,rel,hp,atk,defense,frame,cycle',CASES)
def test_actual_two_normals_unequal_DEF_realDP_HP_noSP(name,rel,hp,atk,defense,frame,cycle):
    s=make(rel);s.advance(frame+cycle+3)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    starts=[e for e in s.session.events if e['type']=='ability.started']
    assert len(hits)==2 and hits[0]['time']-starts[0]['time']==frame
    assert hits[1]['time']-hits[0]['time']==cycle
    assert [e['payload']['amount'] for e in hits]==[atk-137,atk-137]
    assert s.ctx.resources.current('blocker','hp')==10101-2*(atk-137)
    assert s.ctx.resources.current('system/battle','dp')==13
    assert s.ctx.resources.current('enemy','hp')==hp and set(s.ctx.get('enemy',('resources',)))=={'hp'}


@pytest.mark.parametrize('name,rel,hp,atk,defense,frame,cycle',CASES)
def test_actual_preimpact_CP_disk_and_head_exact_events(name,rel,hp,atk,defense,frame,cycle,tmp_path):
    s=make(rel);s.advance(frame-2);cp=tmp_path/(name+'.json');pin=write_ordered(cp,s.checkpoint())
    r=Engine.restore(s.program,load_bound(cp,pin));s.advance(cycle+7);r.advance(cycle+7)
    assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay()).checkpoint()


def test_sotisd_native_taunt_is_live_modifier_and_can_be_removed():
    s=make(CASES[1][1]);s.advance(2)
    row=next(b for b in s.ctx.get('enemy',('buffs','instances')) if b['definition']=='buff/ch7/source/sotisd_t')
    assert s.ctx.attributes.value('enemy','taunt_level')==1
    s.ctx.buffs.remove('enemy',row['id'])
    assert s.ctx.attributes.value('enemy','taunt_level')==0


def test_sotihd_target_DEF_at_hit_and_source_ASPD_three():
    p=package(CASES[0][1]);p['buffs']=[{'id':'buff/peer/aspeed','kind':'buff',
        'modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':2}]}]
    p['entities'][0]['components']['buffs']={'initial':['buff/peer/aspeed']}
    s=Engine.create(Compiler().compile(p),seed=7192)
    s.submit({'action':'deploy','entity':'unit/peer/current/blocker','row':0,'col':0,'alias':'blocker'},at=0)
    s.advance(5);s.ctx.set('blocker',('attributes','base','def'),287);s.advance(5)
    hit=next(e for e in s.session.events if e['type']=='damage.accepted')
    start=next(e for e in s.session.events if e['type']=='ability.started')
    assert hit['time']-start['time']==6 and hit['payload']['amount']==63
