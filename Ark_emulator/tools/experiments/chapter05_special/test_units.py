import json
from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]
HAMMER='unit/ch5/special/enemy_1045_hammer';LUNMAG='unit/ch5/special/enemy_1038_lunmag'


def fixture(unit=HAMMER):
    p=json.loads((ROOT/'packages/campaign/chapter05_units/special/model.ranged_guard.reference.json').read_bytes())
    hero={'id':'unit/guard','kind':'entity','tags':['player'],'components':{'attributes':{'base':{
        'max_hp':100000,'atk':0,'def':37,'mres':25,'block_count':3}},'deployable':{'cost':0,'terrain':1},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
        'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
    p['entities'].append(hero)
    item={'definition':unit,'instanceAlias':'enemy','position':{'row':0,'col':0}}
    if unit==HAMMER:item['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}
    p['scenarioDraft']={'id':'scene/special','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':5},
        'initialEntities':[item,{'definition':'unit/guard','instanceAlias':'guard','deployed':True,'position':{'row':0,'col':1}}]}
    return p


def test_hammer_two_attacks_charge_real_cost_stun_third_then_target_block_release():
    s=Engine.create(Compiler().compile(fixture()),seed=545);s.advance(200)
    assert s.ctx.resources.current('enemy','sp')==2
    r=Engine.restore(s.program,s.checkpoint());s.advance(90);r.advance(90)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    starts=[(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started']
    # Initial behavior pass precedes first movement blocking reconciliation;
    # real blocking.changed is t0, next decision starts the first cast at t1.
    assert starts[:3]==[(1,'ability/ch5/special/enemy_1045_hammer/normal'),(106,'ability/ch5/special/enemy_1045_hammer/normal'),(211,'ability/ch5/special/enemy_1045_hammer/stun')]
    packets=[e for e in s.session.events if e['type']=='damage.accepted']
    assert [(e['time'],e['payload']['amount']) for e in packets[:3]]==[(29,963),(134,963),(239,963)]
    assert all(packet['time']-start[0]==28 for packet,start in zip(packets[:3],starts[:3]))
    assert s.ctx.resources.current('enemy','sp')==1
    assert s.ctx.buffs.controls('guard')['block'] is False and s.ctx.get('enemy',('runtime','blocked_by')) is None


def test_hammer_intrinsic_stun_immunity_keeps_block_and_damage_sp_still_correct():
    p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'abnormal_immunes':[0]}}
    s=Engine.create(Compiler().compile(p),seed=545);s.advance(240)
    assert s.ctx.buffs.controls('guard')['block'] is True
    assert s.ctx.get('enemy',('runtime','blocked_by'))==s.session.world.resolve('guard')
    assert s.ctx.resources.current('enemy','sp')==1
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_lunmag_single_slot_magic_frame21_plusflight_and_cp_replay():
    s=Engine.create(Compiler().compile(fixture(LUNMAG)),seed=538);s.advance(22)
    r=Engine.restore(s.program,s.checkpoint());s.advance(123);r.advance(123)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']
    assert hits==[(24,300),(144,300)]
    assert len([e for e in s.session.events if e['type']=='attack.accepted'])==2
