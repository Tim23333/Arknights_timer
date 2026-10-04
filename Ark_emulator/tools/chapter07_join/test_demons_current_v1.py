"""Exact demon variants: independent arithmetic with current source-mode clocks."""
import json
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[2]
NAMES=['enemy_1084_sotidm','enemy_1085_sotiwz','enemy_1085_sotiwz_2']


def package(name):
    p=json.loads((ROOT/'packages/campaign/chapter07_boss/demons'/(name+'.module.v1.json')).read_bytes())
    uid=p['entities'][0]['id'];p['entities'].append({'id':'unit/peer/demons/recipient','kind':'entity',
        'tags':['player','ground'],'components':{'attributes':{'base':{
            'max_hp':19000,'atk':0,'def':173,'mres':27,'block_count':1}},
            'resources':{'hp':{'initial':19000,'capacity':19000,'role':'health'}},
            'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},
            'spatial':{},'deployable':{'terrain':'ground','base_cost':7,'capacity':1,'cooldown_seconds':0},
            'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['selectors'].append({'id':'selector/demons/peer/source','kind':'selector',
        'region':{'type':'all'},'filters':[{'tag':'enemy'}]})
    p['scenarioDraft']={'id':'scene/peer/demons/current/'+name,'ruleset':'ruleset/ark_standard',
        'map':{'rows':1,'cols':5},'objectives':{},'resources':{'dp':{'initial':20,'capacity':99}},
        'roster':['unit/peer/demons/recipient'],'initialEntities':[{
            'definition':uid,'instanceAlias':'enemy','position':{'row':0,'col':0},
            'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':4},'checkpoints':[]}}]}
    return p


def run(name,mode1=False,aspeed=False):
    p=package(name)
    if mode1:p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'transition','state':'mode1','selector':'selector/demons/peer/source'}}]
    if aspeed:
        p['buffs'].append({'id':'buff/peer/demons/aspeed','kind':'buff',
            'modifiers':[{'attribute':'attack_speed_ratio','layer':'flat','value':2}]})
        p['entities'][0]['components']['buffs']['initial'].append('buff/peer/demons/aspeed')
    s=Engine.create(Compiler().compile(p),seed=7194)
    s.submit({'action':'deploy','entity':'unit/peer/demons/recipient','row':0,'col':0,'alias':'recipient'},at=0)
    return s


@pytest.mark.parametrize('mode1,frame,expected',[(False,16,307),(True,29,350.4)])
def test_actual_warrior_mode_own_frame_and_unequal_damage(mode1,frame,expected):
    s=run(NAMES[0],mode1);s.advance(frame+5)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    starts=[e for e in s.session.events if e['type']=='ability.started']
    assert len(hits)==1 and hits[0]['time']-starts[0]['time']==frame
    assert hits[0]['payload']['amount']==pytest.approx(expected)
    assert s.ctx.resources.current('enemy','hp')==8000 and s.ctx.resources.current('system/battle','dp')==13


@pytest.mark.parametrize('name,attack',[(NAMES[1],350),(NAMES[2],450)])
def test_actual_caster_timeMode2_not_speed3_attackclock_noSP(name,attack):
    s=run(name,aspeed=True);s.advance(151)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    starts=[e for e in s.session.events if e['type']=='ability.started']
    assert len(hits)==2 and hits[1]['time']-hits[0]['time']==150
    assert all(e['payload']['amount']==pytest.approx(attack*.73) for e in hits)
    assert all('/immo0' in e['payload']['ability'] for e in starts)
    assert set(s.ctx.get('enemy',('resources',)))=={'hp'}


@pytest.mark.parametrize('name',NAMES)
def test_actual_both_modes_public_CP_and_head(name,tmp_path):
    s=run(name);p=s.program;s.advance(2);file=tmp_path/(name+'.json');pin=write_ordered(file,s.checkpoint())
    r=Engine.restore(p,load_bound(file,pin));s.advance(50);r.advance(50)
    assert s.checkpoint()==r.checkpoint()==replay(p,s.export_replay()).checkpoint()
