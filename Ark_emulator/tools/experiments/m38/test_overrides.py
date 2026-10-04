"""Static prototype rules must apply to actual initial/spawn components."""
import pytest
from tools.experiments.m38.test_fields import fixture,Compiler,Engine


@pytest.mark.parametrize('override',[{'abilities':['ability/in']},{'spatial':{'route':{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':2},'checkpoints':[]}}}])
def test_initial_entity_effective_override_is_rejected(override):
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/field','position':{'row':0,'col':1},'components':override})
    with pytest.raises(ValueError,match='static tile field'):Compiler().compile(p)


def test_initial_entity_field_role_cannot_be_changed_to_player():
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/field','position':{'row':0,'col':1},'tags':['player']})
    with pytest.raises(ValueError,match='runtime role'):Compiler().compile(p)


def test_runtime_create_override_rejects_without_world_mutation():
    s=Engine.create(Compiler().compile(fixture()));before=s.checkpoint()
    with pytest.raises(ValueError,match='static tile field'):
        s.ctx.lifecycle.create('unit/field',{'row':0,'col':1},component_overrides={'abilities':['ability/in']})
    assert s.checkpoint()==before


def test_static_owner_cannot_start_ability_after_lowlevel_data_injection():
    s=Engine.create(Compiler().compile(fixture()));owner=s.ctx.state()['tile_fields']['0:1']['owner']
    # Deliberate low-level mutation is not public command evidence; it probes
    # the final consumer guard independently of the authoring compiler.
    s.ctx.set(owner,('abilities',),['ability/in']);before=s.checkpoint()
    with pytest.raises(ValueError,match='not an ability source'):s.ctx.abilities.start(owner,'ability/in')
    assert s.checkpoint()==before


def test_scene_route_argument_and_runtime_route_argument_are_both_rejected():
    route={'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':2},'checkpoints':[]}
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/field','position':{'row':0,'col':1},'route':route})
    with pytest.raises(ValueError,match='static tile field'):Compiler().compile(p)
    s=Engine.create(Compiler().compile(fixture()));before=s.checkpoint()
    with pytest.raises(ValueError,match='route argument'):s.ctx.lifecycle.create('unit/field',{'row':0,'col':1},route=route)
    assert s.checkpoint()==before


def test_instance_owner_parameter_rejected_before_scene_creation():
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/field','position':{'row':0,'col':1},'parameters':{'owner':'target'}})
    with pytest.raises(ValueError,match='owner parameter'):Compiler().compile(p)
