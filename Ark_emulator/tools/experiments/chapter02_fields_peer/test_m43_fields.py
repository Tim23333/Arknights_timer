"""Independent source-bound field inputs; no author fixture imports."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m43_request_transform_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
def load(name):return json.loads((ROOT/'packages/campaign'/name).read_bytes())
def state():return {'side':0,'motion':1,'category':1,'profession':0,'unit_type':1,'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False,'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[]}
def fixture():
    p=load('chapter02_tiles/fields.lossless_request.model.json');operands=load('chapter02_tiles/buffs.lossless_request.model.json');p['rules']+=operands['rules']
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

def healing_fixture():
    p=fixture();p['abilities'][0]['activation']['on_start']=[]
    p['rules']=[r for r in p['rules'] if r['id']!='rule/ch2/gazebo_flying_scale']
    board={'HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO':.03};p['scenarioDraft']['map']['tiles'][1].update(tileKey='tile_healing',blackboard=board)
    p['scenarioDraft']['map']['tile_mechanics']={'tile_healing':{'type':'occupancy_buff_field','definition':'unit/ch2/field/tile_healing','expected_blackboard':board}}
    caster=next(u for u in p['entities'] if u['id']=='unit/caster');caster['components']['attributes']['base'].update(max_hp=800,hp_ratio_recovery=0)
    caster['components']['resources']['hp']={'initial':400,'capacity_attribute':'max_hp','role':'health','recovery_rule':'rule/ch2/tile_hp_ratio_recovery','recovery':{'mode':'continuous'},'parameters':{'healing_allowed':False}}
    return p

def test_exact_maxhp_regen_is_not_heal_packet_and_heal_immunity_does_not_reclassify():
    p=healing_fixture();s=Engine.create(Compiler().compile(p));s.advance(30)
    assert s.ctx.resources.current('caster','hp')==pytest.approx(400+800*.03)
    assert not any(e['type'] in ('healing.accepted','regeneration.accepted') for e in s.session.events)

def test_native_disabled_option_payload_is_retained_without_becoming_live_filter():
    p=fixture();selector=next(x for x in p['selectors'] if x['id']=='selector/ch2/field/tile_gazebo')
    configuration=selector['eligibility']['parameters']['source_configuration']
    configuration.update(_abnormalFlag=99999,_abnormalCombo=-1,_excludeAbnormalFlag='unread_native_disabled')
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'caster','ability':'ability/hit'},at=0);s.advance(1)
    assert s.ctx.resources.current('enemy','hp')==4710

def test_neutral_character_does_not_receive_virtual_ally_field():
    p=healing_fixture();next(u for u in p['entities'] if u['id']=='unit/caster')['components']['selection_state']['side']=2
    s=Engine.create(Compiler().compile(p));s.advance(30);assert s.ctx.resources.current('caster','hp')==400

def test_two_healing_cells_keep_independent_member_identity_after_public_transfer():
    p=healing_fixture();p['scenarioDraft']['map']['tiles'][2]=deepcopy(p['scenarioDraft']['map']['tiles'][1])
    p['abilities'][0]['activation']['on_start']=[{'op':'move','target':'source','position':{'row':0,'col':2}}]
    program=Compiler().compile(p);s=Engine.create(program,seed=4214);s.submit({'action':'skill','source':'caster','ability':'ability/hit'},at=15);s.advance(30)
    assert s.ctx.resources.current('caster','hp')==pytest.approx(424)
    fields=s.ctx.state()['tile_fields'];left=fields['0:1']['owner'];right=fields['0:2']['owner'];assert left!=right
    members=s.ctx.get('caster',('buffs','instances'));assert len(members)==1 and members[0]['source']==right
    assert s.snapshot()==replay(program,s.export_replay()).snapshot()

def test_transform_preserves_arbitrary_nested_request_values_order_locks_and_negative_zero():
    import math
    from ark_sim.domains.request_transforms import request_field_transform
    from ark_sim.contracts import freeze,thaw
    request={'op':'damage','metadata':{'z':True,'a':1,'nested':[0,-0.,{'locks':['x','y']}]},'parameters':{'damage_hook_locks':['buff/a'],'value':1200,'per_distance':1},
             'distance':.5,'amount':19,'rules':{'damage.pipeline':'rule/custom'},'scale':2,'last':None}
    original=deepcopy(request);out=request_field_transform({'effect':freeze(request)},{'field':'scale','factor':1.7,'default':1},{})
    expected=deepcopy(request);expected['scale']=3.4
    assert out['effect']==expected and request==original and list(out['effect'])==list(request)
    assert math.copysign(1,out['effect']['metadata']['nested'][1])==-1
    out['effect']['metadata']['nested'][2]['locks'].append('mutation');assert thaw(freeze(request))==original

@pytest.mark.parametrize('params',[{'field':'_private','factor':2,'default':1},{'field':'scale','factor':True,'default':1},
    {'field':'scale','factor':float('nan'),'default':1},{'field':'scale','factor':float('inf'),'default':1},
    {'field':'scale','factor':1e308,'default':2},{'field':'scale','factor':2,'default':True}])
def test_transform_invalid_input_never_mutates_original_request(params):
    from ark_sim.domains.request_transforms import request_field_transform
    request={'scale':2,'nested':{'value':[1,2]}};before=deepcopy(request)
    with pytest.raises(ValueError):request_field_transform({'effect':request},params,{})
    assert request==before

def test_actual_custom_pipeline_retains_extra_amount_and_nested_parameters_with_public_replay():
    p=fixture();p['rules'].append({'id':'rule/custom','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[
        {'id':'result','expression':"{'accepted':True,'amount':inputs.effect.amount + inputs.effect.parameters.vector[1],'allocations':[],'events':[]}"}], 'output':'nodes.result'}})
    p['abilities'][0]['activation']['on_start'][0]={'op':'damage','damage_type':'true','amount':25,'parameters':{'vector':[11,3],'damage_hook_locks':['buff/unrelated']},
        'metadata':{'retained':{'truth':True,'number':1}},'rules':{'damage.pipeline':'rule/custom'}}
    program=Compiler().compile(p);s=Engine.create(program,seed=4215);s.submit({'action':'skill','source':'caster','ability':'ability/hit'},at=0);s.advance(1)
    assert s.ctx.resources.current('enemy','hp')==4972 and s.snapshot()==replay(program,s.export_replay()).snapshot()
