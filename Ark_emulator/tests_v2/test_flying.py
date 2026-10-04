"""Independent straight-segment flight evidence, without native enemy IDs."""
from copy import deepcopy

import pytest

from ark_sim import Compiler, Engine
from ark_sim.content.repository import ContentError
from ark_sim.domains.spatial import GridTopology, UnreachablePathError, route_motion_mode
from ark_sim.presets.providers import spatial_blocking
from ark_sim.rules.errors import RuleError
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def package(mode='FLY',checkpoints=None,wall=False,blocker=False):
    tiles=[{'tileKey':'tile_floor','passableMask':1,'buildableType':1} for _ in range(15)]
    if wall:
        for row in range(3):
            tiles[row*5+2]={'tileKey':'tile_wall','passableMask':0,'buildableType':0}
    route={'motionMode':mode,'startPosition':{'row':1,'col':0},'endPosition':{'row':1,'col':4},
           'checkpoints':checkpoints or []}
    units=[{'id':'unit/mover','kind':'entity','tags':['enemy'], 'components':{
        'attributes':{'base':{'max_hp':100,'move_speed':1,'block_cost':1}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{}}}]
    initial=[{'definition':'unit/mover','instanceAlias':'mover','position':{'row':1,'col':0},'route':route}]
    if blocker:
        units.append({'id':'unit/blocker','kind':'entity','tags':['player'],'components':{
            'attributes':{'base':{'max_hp':100,'block_count':1,'redeploy_time':1}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},
            'deployable':{'cost':0,'cooldown_seconds':1}}})
        initial.append({'definition':'unit/blocker','instanceAlias':'blocker','position':{'row':1,'col':2}})
    return {'schemaVersion':2,'entities':units,'scenarioDraft':{
        'id':'scenario/flying_probe','ruleset':'ruleset/ark_standard',
        'map':{'rows':3,'cols':5,'tiles':tiles},'initialEntities':initial}}


def simulation(**kwargs):
    return Engine.create(Compiler().compile(package(**kwargs)),seed=37)


@pytest.mark.parametrize('mode',['FLY',1,{'name':'FLY'},{'name':'FLY','value':1}])
def test_flight_crosses_complete_wall_by_declared_straight_segment(mode):
    sim=simulation(mode=mode,wall=True)
    sim.advance(61)
    point=sim.ctx.get('mover',('spatial','position'))
    assert point['row']==1
    assert point['col']==pytest.approx(61/30)
    assert sim.ctx.spatial.blocked_by('mover') is None
    path=sim.ctx.get('mover',('spatial','movement_path'))
    assert path==[{'row':1,'col':4}]


def test_ground_cannot_cross_the_same_wall():
    sim=simulation(mode='WALK',wall=True)
    with pytest.raises(RuleError,match='No ground route') as failure:
        sim.advance(1)
    assert isinstance(failure.value.__cause__,UnreachablePathError)
    assert sim.ctx.get('mover',('spatial','position'))=={'row':1,'col':0}


def test_flying_ignores_ground_interception_and_does_not_use_capacity():
    sim=simulation(blocker=True)
    sim.advance(75)
    assert sim.ctx.get('mover',('spatial','position'))['col']==pytest.approx(2.5)
    assert sim.ctx.spatial.blocked_by('mover') is None
    assert not [e for e in sim.session.events if e['type']=='blocking.changed']
    ground=simulation(mode='WALK',blocker=True)
    ground.advance(75)
    assert ground.ctx.spatial.blocked_by('mover')==ground.session.world.resolve('blocker')
    assert ground.ctx.get('mover',('spatial','position'))['col']<2


def test_stale_ground_blocking_is_cleared_without_one_tick_flight_stall():
    sim=simulation(blocker=True)
    sim.ctx.set('mover',('runtime','blocked_by'),sim.session.world.resolve('blocker'))
    sim.advance(1)
    assert sim.ctx.get('mover',('spatial','position'))['col']==pytest.approx(1/30)
    assert sim.ctx.spatial.blocked_by('mover') is None
    changes=[e for e in sim.session.events if e['type']=='blocking.changed']
    assert len(changes)==1 and changes[0]['payload']['reason']=='flying'


def test_blocking_provider_independently_rejects_flight():
    p={'row':1,'col':1}
    target={'components':{'spatial':{'position':p,'route':{'motionMode':1}}}}
    result=spatial_blocking({'blocker':{'components':{'spatial':{'position':p}}},'target':target},{},{})
    assert result=={'accepted':False,'reason':'flying'}


def test_declared_move_checkpoint_and_wait_are_not_skipped():
    cps=[{'type':'MOVE','position':{'row':0,'col':0}},
         {'type':'WAIT_FOR_SECONDS','time':1},
         {'type':'MOVE','position':{'row':0,'col':4}}]
    sim=simulation(checkpoints=cps,wall=True)
    sim.advance(15)
    assert sim.ctx.get('mover',('spatial','position'))==pytest.approx({'row':0.5,'col':0})
    sim.advance(40)
    point=sim.ctx.get('mover',('spatial','position'))
    assert point=={'row':0,'col':0}
    waits=[e for e in sim.session.events if e['type']=='movement.wait']
    assert len(waits)==1
    until=waits[0]['payload']['until']
    sim.advance(until-sim.session.time)
    assert sim.ctx.get('mover',('spatial','position'))==point
    sim.advance(15)
    point=sim.ctx.get('mover',('spatial','position'))
    assert point['row']==0 and point['col']==pytest.approx(0.5)
    assert sim.ctx.get('mover',('spatial','movement'))['checkpoint']==2


def test_flight_segment_is_geometrically_straight_and_keeps_fractional_endpoint():
    grid=GridTopology({'rows':3,'cols':5})
    assert grid.path({'row':1,'col':0},{'row':0.25,'col':3.5},1)==[{'row':0.25,'col':3.5}]
    data=package()
    data['scenarioDraft']['initialEntities'][0]['route']['endPosition']={'row':2,'col':4}
    sim=Engine.create(Compiler().compile(data))
    sim.advance(30)
    point=sim.ctx.get('mover',('spatial','position'))
    assert point['row']==pytest.approx(1+1/(17**0.5))
    assert point['col']==pytest.approx(4/(17**0.5))


def test_consecutive_waits_execute_in_order_instead_of_becoming_a_move():
    sim=simulation(checkpoints=[{'type':'WAIT_FOR_SECONDS','time':0.5},
                               {'type':'WAIT_FOR_SECONDS','time':0.5}])
    sim.advance(30)
    assert sim.ctx.get('mover',('spatial','position'))=={'row':1,'col':0}
    waits=[e for e in sim.session.events if e['type']=='movement.wait']
    assert [e['payload']['until'] for e in waits]==[15,30]
    sim.advance(1)
    assert sim.ctx.get('mover',('spatial','position'))['col']==pytest.approx(1/30)


def test_flight_exit_keeps_lifecycle_leak_settlement():
    sim=simulation(wall=True)
    sim.advance(123)
    assert sim.ctx.get('mover',('spatial','position'))=={'row':1,'col':4}
    assert sim.ctx.get('mover',('runtime','state'))=='exited'
    assert sim.ctx.state()['leaks']==1


def test_flystart_is_geometry_only_not_a_ground_floor():
    data=package(wall=True)
    data['scenarioDraft']['map']['tiles'][5]={'tileKey':'tile_flystart','passableMask':2,'buildableType':0}
    sim=Engine.create(Compiler().compile(data))
    sim.advance(1)
    assert sim.ctx.get('mover',('spatial','position'))['col']==pytest.approx(1/30)
    grid=GridTopology(data['scenarioDraft']['map'])
    assert not grid.passable(1,0)
    with pytest.raises(UnreachablePathError,match='not ground-passable'):
        grid.path({'row':1,'col':0},{'row':1,'col':4},0)


@pytest.mark.parametrize('mode',['E_NUM',999,2,True,{'name':'E_NUM','value':2},{'name':'FLY','value':0}])
def test_unknown_or_inconsistent_motion_modes_still_fail(mode):
    with pytest.raises(ContentError):
        Compiler().compile(package(mode=mode))
    with pytest.raises(ValueError):
        route_motion_mode({'motionMode':mode})


def test_special_tile_mechanics_are_not_relaxed_for_flight():
    data=package()
    data['scenarioDraft']['map']['tiles'][0]={'tileKey':'tile_volcano','passableMask':2}
    with pytest.raises(ContentError,match='unsupported tile mechanic'):
        Compiler().compile(data)


def test_flight_keeps_checkpoint_restore_and_input_replay_identical():
    data=package(wall=True,blocker=True,checkpoints=[{'type':'WAIT_FOR_SECONDS','time':0.5},
          {'type':'MOVE','position':{'row':0,'col':4}}])
    program=Compiler().compile(data)
    sim=Engine.create(program,seed=37)
    sim.advance(65)
    checkpoint=sim.checkpoint()
    sim.advance(100)
    expected=sim.snapshot()
    resumed=Engine.restore(program,checkpoint)
    resumed.advance(100)
    assert first_difference(expected,resumed.snapshot()) is None
    assert first_difference(expected,replay(program,sim.export_replay()).snapshot()) is None
