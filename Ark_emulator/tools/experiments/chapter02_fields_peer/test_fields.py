"""Independent source-bound field inputs; no author fixture imports."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
def load(name):return json.loads((ROOT/'packages/campaign'/name).read_bytes())
def state():return {'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[]}
def fixture():
    p=load('chapter02_tiles/fields.reference_model.json');operands=load('chapter02_tiles/buffs.motion_state.partial.json');p['rules']+=operands['rules']
    p['entities'].append({'id':'unit/caster','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':state(),
        'attributes':{'base':{'max_hp':1000,'atk':200,'attack_speed_ratio':1}},'resources':{'hp':{'initial':500,'capacity':1000,'role':'health'}},'abilities':['ability/hit']}})
    p['entities'].append({'id':'unit/enemy','kind':'entity','tags':['enemy'],'components':{'spatial':{},'selection_state':{**state(),'side':1,'motion':2},
        'attributes':{'base':{'max_hp':5000,'def':50,'mres':20}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}}}})
    p['selectors'].append({'id':'selector/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}]})
    p['abilities']=[{'id':'ability/hit','kind':'ability','selector':'selector/enemy','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]}]
    board={'atk_scale':1.7,'attack_speed':-20.0};p['scenarioDraft']={'id':'scene/field/independent','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3,'tiles':[
        {'tileKey':'tile_floor','passableMask':1,'buildableType':1},{'tileKey':'tile_gazebo','passableMask':3,'buildableType':0,'blackboard':board},{'tileKey':'tile_floor','passableMask':1,'buildableType':1}],
        'tile_mechanics':{'tile_gazebo':{'type':'occupancy_buff_field','definition':'unit/ch2/field/tile_gazebo','expected_blackboard':board}}},
        'initialEntities':[{'definition':'unit/caster','instanceAlias':'caster','position':{'row':0,'col':1}},{'definition':'unit/enemy','instanceAlias':'enemy','position':{'row':0,'col':2}}]}
    return p
def test_source_physical_boost_is_pre_defense_not_post_defense():
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=4211);s.submit({'action':'skill','source':'caster','ability':'ability/hit'},at=0);s.advance(1)
    assert s.ctx.resources.current('enemy','hp')==5000-(200*1.7-50)
    assert s.snapshot()==replay(program,s.export_replay()).snapshot()
def test_source_arts_boost_resistance_and_ability_scale_compose():
    p=fixture();p['abilities'][0]['activation']['on_start'][0].update(damage_type='arts',scale=2)
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'caster','ability':'ability/hit'},at=0);s.advance(1)
    assert s.ctx.resources.current('enemy','hp')==pytest.approx(5000-200*2*1.7*.8)
def test_real_fixed_weedy_distance_pipeline_can_compose_without_required_attack_operands():
    p=fixture();weedy=load('skills.weedy.json');rule=next(r for r in weedy['rules'] if r['id']=='rule/campaign_weedy_distance_damage');p['rules'].append(deepcopy(rule))
    p['abilities'][0]['activation']['on_start'][0]={'op':'damage','damage_type':'true','distance':.5,'parameters':{'value':1200,'per_distance':1},'rules':{'damage.pipeline':rule['id']}}
    program=Compiler().compile(p);s=Engine.create(program,seed=4212);s.submit({'action':'skill','source':'caster','ability':'ability/hit'},at=0);s.advance(1)
    # Exact existing rule reads distance*value/per_distance, and does not bind ATK/DEF/RES or consume scale.
    assert s.ctx.resources.current('enemy','hp')==4400
