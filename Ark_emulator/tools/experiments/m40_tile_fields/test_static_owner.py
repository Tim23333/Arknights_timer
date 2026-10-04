"""A tile owner must not quietly walk away from its declared cell."""
from copy import deepcopy
import pytest
from tools.experiments.m40_tile_fields.test_fields import fixture,Compiler,Engine


@pytest.mark.parametrize('key,value',[('route',{'motionMode':'WALK','startPosition':{'row':0,'col':1},'endPosition':{'row':0,'col':2},'checkpoints':[]}),
    ('route_id','author/route'),('movement',{}),('steering',{}),('wait_seconds',1),('block_capacity',1)])
def test_owner_motion_or_driver_fields_rejected_at_compile(key,value):
    p=fixture();p['entities'][0]['components']['spatial'][key]=value
    # route_id is rejected earlier by the existing route resolver; all other
    # fields reach the new static-owner gate. Neither path permits a driver.
    with pytest.raises(ValueError,match='route ID resolution' if key=='route_id' else 'static tile field'):Compiler().compile(p)


def test_public_buff_move_effect_cannot_move_internal_owner():
    p=fixture();p['buffs'][0]['effects']=[{'op':'move','target':'source','position':{'row':0,'col':2}}];p['buffs'][0]['interval_seconds']=1/30
    s=Engine.create(Compiler().compile(p),seed=32);owner=s.ctx.state()['tile_fields']['0:1']['owner'];s.advance(3)
    assert s.ctx.get(owner,('spatial','position'))=={'row':0,'col':1}
    assert s.ctx.state()['tile_fields']['0:1']['owner']==owner
