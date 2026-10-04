"""Actual map Blackboard data cannot masquerade as references/providers."""
import pytest
from tools.experiments.m39_tile_fields.test_fields import fixture,Compiler,Engine


@pytest.mark.parametrize('values',[{'provider':1,'rule':2},{'provider':'native_style','rule':'some_data','definition':'label'}, {'buff':0.1,'ability':False}])
def test_mapping_board_reference_names_are_preserved_as_data(values):
    p=fixture();p['scenarioDraft']['map']['tiles'][1]['blackboard']=values
    p['scenarioDraft']['map']['tile_mechanics']['custom_rest_cell']['expected_blackboard']=values
    program=Compiler().compile(p);s=Engine.create(program)
    assert s.ctx.state()['tile_fields']['0:1']['source_blackboard']==values
    assert 'native_style' not in program.metadata.get('providers',{})


def test_real_field_rule_and_effect_references_still_validate():
    p=fixture();p['buffs'][0]['aura']['buff']='missing/member'
    with pytest.raises(ValueError):Compiler().compile(p)
    p=fixture();p['rules'][0]['implementation']={'type':'provider','provider':'missing/actual_provider'}
    with pytest.raises(ValueError,match='provider|Provider'):Compiler().compile(p)


def test_blackboard_existing_definition_and_tags_are_not_actor_overrides():
    p=fixture();values={'definition':'unit/target','tags':['tile_field_owner']}
    p['scenarioDraft']['map']['tiles'][1]['blackboard']=values
    p['scenarioDraft']['map']['tile_mechanics']['custom_rest_cell']['expected_blackboard']=values
    s=Engine.create(Compiler().compile(p));assert s.ctx.state()['tile_fields']['0:1']['source_blackboard']==values
