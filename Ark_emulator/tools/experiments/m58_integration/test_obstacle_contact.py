from pathlib import Path
import sys
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter03_crate_module import build
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture(rows=1):
    p=build();crate=p['entities'][0]
    crate['components']['route_obstacle']={'rule':'rule/route_obstacle','contact_radius':.45,'parameters':{}}
    p['rules']=[{'id':'rule/route_obstacle','kind':'rule','contract':'blocking.obstacle','implementation':{'type':'expression','expression':'inputs.source.components.selection_state.side != inputs.obstacle.components.selection_state.side'}}]
    p['entities'].append({'id':'unit/test_enemy','kind':'entity','tags':['enemy','ground'],'components':{
        'spatial':{},'selection_state':{'side':1,'motion':1,'category':1},'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'move_speed':3,'attack_interval':1,'block_cost':1}},
        'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'abilities':['ability/attack'],
        'behavior':{'machine':'behavior/enemy'},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['abilities']=[{'id':'ability/attack','kind':'ability','selector':'selector/blocker','activation':{'mode':'automatic_attack','parameters':{'auto_only':True}},
        'timeline':[{'at_seconds':.1,'effect':{'op':'damage','damage_type':'physical'}}]}]
    p['selectors']=[{'id':'selector/blocker','kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1}]
    p['behaviors']=[{'id':'behavior/enemy','kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],
        'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'normal','selector':'selector/blocker'}],
            'cast_groups':[{'key':'normal','abilities':['ability/attack']}],'parameters':{'target_key':'normal','blocked_target':True,'stop_on_target':False,'stop_cast_groups':['normal']}}]}}]
    p['scenarioDraft']={'id':'scene/selected_obstacle','ruleset':'ruleset/ark_standard','roster':['unit/ch3/crate'],'resources':{
        'dp':{'initial':100,'capacity':100},'crate_cards':{'initial':5,'capacity':5},'life':{'initial':99999,'capacity':99999}},
        'objectives':{'type':'waves','life_resource':'life'},'map':{'rows':rows,'cols':4},
        'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':.1,'fragments':[{'actions':[{
            'kind':'spawn','spawn':{'definition':'unit/test_enemy','instanceAlias':'enemy','position':{'row':0,'col':0},
                'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}}]}]}]}}
    return p


def commands(s):s.submit({'action':'deploy','definition':'unit/ch3/crate','alias':'crate','position':{'row':0,'col':1}},at=0)


def test_route_contact_attacks_source_obstacle_then_resumes_real_lifecycle(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=5501);commands(s);s.advance(6)
    assert s.ctx.alive('crate')
    path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.advance(45);r.advance(45)
    assert not s.ctx.alive('crate') and s.ctx.resources.current('crate','hp')==0
    assert not s.ctx.state()['terrain']['layers']
    assert s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','life')==99998
    assert s.ctx.resources.current('system/battle','crate_cards')==4
    assert any(e['type']=='calculation' and e['payload']['calculation_id']=='blocking.obstacle' for e in s.session.events)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_flying_route_does_not_contact_ground_obstacle():
    p=fixture();p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['spawn']['route']['motionMode']='FLY'
    p['entities'][1]['components']['selection_state']['motion']=2;s=Engine.create(Compiler().compile(p));commands(s);s.advance(45)
    assert s.ctx.alive('crate') and s.ctx.resources.current('crate','hp')==100
    assert s.ctx.state()['leaks']==1


def test_declared_rule_can_deny_contact_without_changing_source_category():
    p=fixture();p['rules'][0]['implementation']['expression']='False';s=Engine.create(Compiler().compile(p));commands(s);s.advance(45)
    assert s.ctx.resources.current('crate','hp')==100 and s.ctx.get('crate',('selection_state','category'))==4
    assert s.ctx.state()['leaks']==1


def test_selected_weighted_detour_does_not_attack_off_path_obstacle():
    p=fixture(rows=2);p['entities'][0]['components']['terrain_overlays'][0]['rule']='rule/costs'
    p['rules'].append({'id':'rule/costs','kind':'rule','contract':'terrain.tile_options','implementation':{'type':'provider','provider':'ark.terrain.tile_options'},'parameters':{'obstacle_like_cost':100}})
    s=Engine.create(Compiler().compile(p));commands(s);s.advance(60)
    assert s.ctx.resources.current('crate','hp')==100 and s.ctx.state()['leaks']==1
    assert not any(e['type']=='calculation' and e['payload']['calculation_id']=='blocking.obstacle' for e in s.session.events)


@pytest.mark.parametrize('change',[lambda p:p['entities'][0]['components']['route_obstacle'].update(contact_radius=True),
    lambda p:p['entities'][0]['components']['route_obstacle'].update(contact_radius=-1),
    lambda p:p['entities'][0]['components']['route_obstacle'].update(rule='selector/blocker'),
    lambda p:p['entities'][0]['components']['route_obstacle'].update(unknown=True)])
def test_unknown_or_invalid_route_obstacle_schema_compile_reject(change):
    p=fixture();change(p)
    with pytest.raises(ValueError):Compiler().compile(p)


def test_failure_after_real_contact_calculation_rolls_back_public_command_all_partitions():
    p=fixture();p['rules'][0]['implementation']['expression']='1 / 0'
    # Enemy at same cell allows creation/blocking to consume the actual custom
    # rule during the deploy command; original actor, stock/DP and tasks survive.
    p['scenarioDraft'].pop('timeline');p['scenarioDraft']['objectives']={}
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/test_enemy','instanceAlias':'enemy','position':{'row':0,'col':1},
        'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':3},'checkpoints':[]}}]
    s=Engine.create(Compiler().compile(p));before=s.checkpoint()
    with pytest.raises(Exception):
        with s.session.atomic():s._execute_command({'action':'deploy','definition':'unit/ch3/crate','position':{'row':0,'col':1}})
    assert s.checkpoint()==before and not s.ctx.spatial._blocking_reconciling


def test_regular_character_blocker_has_priority_over_obstacle_contact():
    p=fixture();p['entities'].append({'id':'unit/ordinary','kind':'entity','tags':['player'],'components':{'spatial':{},
        'attributes':{'base':{'max_hp':10000,'def':0,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'deployable':{'base_cost':0,'terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/ordinary','instanceAlias':'ordinary','position':{'row':0,'col':0},'deployed':True}]
    s=Engine.create(Compiler().compile(p));commands(s);s.advance(10)
    assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('ordinary')
    assert s.ctx.resources.current('crate','hp')==100


def test_multiple_movers_can_attack_same_obstacle_without_normal_capacity_limit():
    p=fixture();p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][0]['count']=2
    # Lower attack makes both actors establish contact before destruction.
    p['entities'][1]['components']['attributes']['base']['atk']=25
    s=Engine.create(Compiler().compile(p));commands(s);s.advance(12)
    relations=[s.ctx.spatial.blocked_by(e['id']) for e in s.session.world.entities() if 'enemy' in e['tags']]
    assert len(relations)==2 and relations==[s.session.world.resolve('crate')]*2
