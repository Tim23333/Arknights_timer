"""Internal field role cannot be acquired by an ordinary hidden attacker."""
import pytest
from tools.experiments.m39_tile_fields.test_fields import fixture,Compiler,Engine


def test_ordinary_initial_actor_cannot_spoof_reserved_role():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['tags']=['tile_field_owner']
    with pytest.raises(ValueError,match='reserved tile field role'):Compiler().compile(p)


def test_ordinary_runtime_create_cannot_spoof_role_without_state_change():
    s=Engine.create(Compiler().compile(fixture()));before=s.checkpoint()
    with pytest.raises(ValueError,match='reserved tile field role'):
        s.ctx.lifecycle.create('unit/target',{'row':0,'col':0},tags=['tile_field_owner'])
    assert s.checkpoint()==before


def test_normal_actor_custom_nonreserved_tags_still_supported():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['tags']=['player','author_custom_role']
    s=Engine.create(Compiler().compile(p));assert s.ctx.selectable('target')


def test_normal_owned_actor_parameter_is_not_rejected_by_field_policy():
    p=fixture();p['scenarioDraft']['initialEntities'].append({'definition':'unit/target','instanceAlias':'owned','position':{'row':0,'col':2},'parameters':{'owner':'target'}})
    s=Engine.create(Compiler().compile(p))
    assert s.ctx.get('owned',('ownership','owner'))==s.session.world.resolve('target')
