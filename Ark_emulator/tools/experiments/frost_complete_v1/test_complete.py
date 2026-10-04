import json
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]
ICE='ability/ch4/frost/ice_shield';NORMAL='ability/frost/normal';BLAST='ability/frost/blast'


def fixture(override=True):
    p=json.loads((ROOT/'packages/campaign/chapter04_boss/frost_complete_v1/module.reference.json').read_bytes())
    hero={'id':'unit/hero','kind':'entity','tags':['player'],'components':{'attributes':{'base':{
        'max_hp':100000,'def':0,'mres':0,'block_count':0}},'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
        'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'abilities':[],
        'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p['entities'].append(hero)
    item={'definition':'unit/ch4/frstar/level0','instanceAlias':'boss','position':{'row':2,'col':2}}
    if override:item['components']={'ability_timing':{'initial_cooldowns':{ICE:0,BLAST:0}}}
    p['scenarioDraft']={'id':'scene/frost_three','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':5,'cols':6},'initialEntities':[item,{'definition':'unit/hero','instanceAlias':'hero','position':{'row':2,'col':3}}]}
    return p


def create(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=41666)
def starts(s):return [(e['time'],e['payload']['ability']) for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==2]


def test_source_three_skills_highest_ice_at0_then_blast_then_normal_and_cp_replay():
    s=create();s.advance(54);assert starts(s)==[(0,ICE)]
    assert s.ctx.get('boss',('runtime','behavior_decision','move')) is False
    assert not any(e['definition_id']=='unit/ch4/frost/sealed_floor' for e in s.session.world.entities())
    r=Engine.restore(s.program,s.checkpoint());s.advance(80);r.advance(80)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert starts(s)==[(0,ICE),(111,BLAST)]
    tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/ch4/frost/sealed_floor']
    assert len(tokens)==2 and all(s.ctx.active(e['id']) and not s.ctx.selectable(e['id']) for e in tokens)
    assert [e['time'] for e in s.session.events if e['type']=='tile.token_created']==[55,55]


def test_actual_initial_cooldowns_and_min2_cells_capture_without_query_random():
    s=create(fixture(False))
    assert s.ctx.get('boss',('runtime','cooldowns',ICE))==900
    assert s.ctx.get('boss',('runtime','cooldowns',BLAST))==255
    s.advance(715)
    assert starts(s)==[(0,NORMAL),(111,NORMAL),(222,NORMAL),(333,BLAST),(444,NORMAL),(555,NORMAL),(666,BLAST)]
    assert not any(e['type']=='tile.selection' for e in s.session.events)
    s.advance(390)
    assert any(a==ICE for _,a in starts(s))
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_true_first_down_cancels_ice_before55_and_restores_three_skill_clocks():
    p=fixture();p['rules'].append({'id':'rule/env','kind':'rule','contract':'damage.pipeline',
        'implementation':{'type':'graph','nodes':[{'id':'packet','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount,'allocations':[],'events':[]}"}],'output':'nodes.packet'}})
    p['scenarioDraft']['scheduledEffects']=[{'at':20,'effect':{'op':'no_source_damage','target':2,
        'fixed_amount':25000,'damage_type':'true','attack_type':'NONE','origin':{'kind':'source_frost_down'},
        'ignore_for_sp':False,'damage_without_modify':False,'node_is_env_damage':False,
        'env_blackboard_injected':True,'environmental':True,'rules':{'damage.pipeline':'rule/env'}}}]
    s=create(p);s.advance(25)
    assert s.ctx.alive('boss') and not s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==0
    r=Engine.restore(s.program,s.checkpoint());s.advance(150);r.advance(150)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert s.ctx.resources.current('boss','hp')==25000 and s.ctx.active('boss')
    assert s.ctx.get('boss',('runtime','cooldowns',ICE))==1070
    assert s.ctx.get('boss',('runtime','cooldowns',BLAST))==425
    assert not any(e['type']=='tile.token_created' for e in s.session.events)
