"""Independent M7 spatial model tests; no native RNG/steering proof implied."""
from copy import deepcopy
import math

import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.spatial import GridTopology,UnreachablePathError
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def model(ranges=None,axes=None,zero=False):
    placement={'rule':'rule/review_spawn','stream':'review_spawn','sample_axes':axes or ['col','row'],
        'sample_zero_range':zero,'random_range':ranges or {'row':.2,'col':.2},'offset':{'row':0,'col':0}}
    return {'schemaVersion':2,'entities':[{'id':'unit/review_enemy','kind':'entity','tags':['enemy'],
        'components':{'attributes':{'base':{'max_hp':100,'move_speed':1,'block_cost':1}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{}}}],
        'rules':[{'id':'rule/review_spawn','kind':'calculation_rule','contract':'spawn.position',
            'implementation':{'type':'provider','provider':'ark.spawn.uniform_rect'},
            'parameters':{'axis_signs':{'row':-1,'col':1}}}],
        'scenarioDraft':{'id':'scenario/m7_review','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':4},
            'waves':[{'at':0,'definition':'unit/review_enemy','instanceAlias':'born','position':{'row':1,'col':0},'placement':placement}]}}


def engine(data):return Engine.create(Compiler().compile(data),seed=703)


@pytest.mark.parametrize('zero,expected',[ (False,0),(True,2)])
def test_zero_range_budget_is_declared_choice_and_position_remains_anchor(zero,expected):
    data=model({'row':0,'col':0},zero=zero);sim=engine(data);sim.advance(1)
    assert len(sim.session.random.samples)==expected
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':0}
    assert sim.ctx.state()['pending_waves']==0


def test_single_active_axis_uses_one_draw_and_declared_sign():
    sim=engine(model({'row':.2,'col':0}));sim.advance(1)
    sample=sim.session.random.samples[0]['value']
    assert len(sim.session.random.samples)==1
    p=sim.ctx.get('born',('spatial','position'))
    assert p['col']==0 and p['row']==pytest.approx(1-(2*sample-1)*.2)


def test_sampling_order_axes_and_full_35_wave_budget_are_observable():
    data=model();proto=data['scenarioDraft']['waves'][0]
    data['scenarioDraft']['waves']=[]
    for i in range(35):
        wave=deepcopy(proto);wave['instanceAlias']=f'born{i}'
        if i in (11,17):wave['placement']['random_range']={'row':0,'col':0}
        data['scenarioDraft']['waves'].append(wave)
    sim=engine(data);sim.advance(1)
    assert len(sim.session.random.samples)==66
    resolved=[e for e in sim.session.events if e['type']=='spawn.position_resolved']
    assert len(resolved)==35
    assert [x['axis'] for x in resolved[0]['payload']['samples']]==['col','row']
    samples=sim.session.random.samples
    p=sim.ctx.get('born0',('spatial','position'))
    assert p=={'row':pytest.approx(1-(2*samples[1]['value']-1)*.2),
               'col':pytest.approx((2*samples[0]['value']-1)*.2)}
    assert not any(s['stream']=='imp' for s in samples)


def test_negative_portal_cell_coordinate_is_not_clamped_to_center_rectangle():
    data=model({'row':0,'col':0});data['scenarioDraft']['waves'][0]['placement']['offset']['col']=-.25
    sim=engine(data);sim.advance(1)
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':-.25}
    assert sim.ctx.spatial.grid._cell({'row':1,'col':-.25})==(1,0)


@pytest.mark.parametrize('offset',[ -.51,3.51])
def test_position_outside_full_cell_envelope_rolls_back_sampling_and_fails_stop(offset):
    data=model();data['scenarioDraft']['waves'][0]['placement']['offset']['col']=offset
    # Remove random col jitter to make the out-of-envelope result exact.
    data['scenarioDraft']['waves'][0]['placement']['random_range']['col']=0
    sim=engine(data);before=deepcopy(sim.checkpoint())
    with pytest.raises(ValueError):sim.advance(1)
    assert not sim.session.random.samples
    assert sim.ctx.state()['pending_waves']==1
    assert len(sim.session.world.entities())==1
    with pytest.raises(RuntimeError,match='restore'):sim.advance(1)
    assert Engine.restore(sim.program,before).checkpoint()==before


def test_failure_after_entity_creation_restores_alias_resources_ids_and_rng():
    data=model();hp=data['entities'][0]['components']['resources']['hp'];hp['capacity']=10
    hp['bounds_rule']='rule/review_reject_bounds'
    data['rules'].append({'id':'rule/review_reject_bounds','kind':'calculation_rule','extends':'rule/ark_resource_bounds',
        'parameters':{'mode':'reject'}})
    sim=engine(data);world=deepcopy(sim.session.world.snapshot());log=deepcopy(sim.session.events)
    with pytest.raises(ValueError):sim.advance(1)
    assert sim.session.world.snapshot()==world and sim.session.events==log
    assert not sim.session.random.samples and sim.ctx.state()['pending_waves']==1
    with pytest.raises(KeyError):sim.session.world.resolve('born')


def test_pure_override_uses_declared_samples_but_can_replace_position_formula():
    data=model();data['rules'][0]['implementation']={'type':'expression',
        'expression':"{'row':inputs.anchor.row+0.25,'col':inputs.anchor.col+1}"}
    sim=engine(data);sim.advance(1)
    assert len(sim.session.random.samples)==2
    assert sim.ctx.get('born',('spatial','position'))=={'row':1.25,'col':1}


def test_fixed_sample_vector_axis_signs_and_offsets_have_independent_expected_position():
    sim=engine(model())
    position=sim.ctx.calc('spawn.position',{'anchor':{'row':4,'col':0},'offset':{'row':-.1,'col':.25},
        'random_range':{'row':.3,'col':.2},'samples':[{'axis':'col','value':.75},{'axis':'row','value':.25}]},
        rule_id='rule/review_spawn')
    assert position=={'row':pytest.approx(4.05),'col':pytest.approx(.35)}
    assert not sim.session.random.samples


def tiles(rows,cols,walls=()):
    return {'rows':rows,'cols':cols,'tiles':[{'tileKey':'tile_wall','passableMask':0} if (r,c) in walls
        else {'tileKey':'tile_floor','passableMask':1} for r in range(rows) for c in range(cols)]}


def test_eight_neighbor_weighted_shortest_path_and_default_four_neighbors():
    grid=GridTopology(tiles(4,4))
    origin={'row':0,'col':0};target={'row':3,'col':3}
    path=grid.path(origin,target,allow_diagonal=True)
    assert path==[{'row':1,'col':1},{'row':2,'col':2},{'row':3,'col':3}]
    assert len(grid.path(origin,target))==6
    points=[origin]+path
    assert sum(math.hypot(b['row']-a['row'],b['col']-a['col']) for a,b in zip(points,points[1:]))==pytest.approx(3*math.sqrt(2))


def test_one_blocked_cardinal_side_prevents_diagonal_shortcut_even_if_other_side_open():
    grid=GridTopology(tiles(2,2,{(0,1)}));start={'row':0,'col':0};goal={'row':1,'col':1}
    assert grid.path(start,goal,allow_diagonal=True)==[{'row':1,'col':0},goal]
    blocked=GridTopology(tiles(2,2,{(0,1),(1,0)}))
    with pytest.raises(UnreachablePathError):blocked.path(start,goal,allow_diagonal=True)


def test_weighted_path_prefers_more_steps_with_smaller_euclidean_cost():
    walls={(0,0),(0,1),(0,5),(1,1),(2,3),(2,4),(3,3),(4,6)}
    grid=GridTopology(tiles(5,7,walls));start={'row':2,'col':0};end={'row':2,'col':6}
    path=grid.path(start,end,allow_diagonal=True)
    points=[start]+path
    cost=sum(math.hypot(b['row']-a['row'],b['col']-a['col']) for a,b in zip(points,points[1:]))
    # A legal six-step bottom detour costs2+4sqrt(2). The seven-step top
    # detour costs6+sqrt(2), so minimizing hop count would be incorrect.
    assert len(path)==7 and cost==pytest.approx(6+math.sqrt(2))
    assert cost < 2+4*math.sqrt(2)
    assert grid.path(start,end,allow_diagonal=True)==path


@pytest.mark.parametrize('field,value',[('sample_axes',['row','row']),('sample_axes',['x','y']),
    ('stream',''),('sample_zero_range',1),('random_range',{'row':-.1,'col':.2})])
def test_illegal_wave_sampler_declarations_fail_compile(field,value):
    data=model();data['scenarioDraft']['waves'][0]['placement'][field]=value
    with pytest.raises(ValueError):Compiler().compile(data)


def test_uniform_provider_rejects_duplicate_samples_without_consuming_rng():
    sim=engine(model())
    with pytest.raises(ValueError):
        sim.ctx.calc('spawn.position',{'anchor':{'row':1,'col':0},'offset':{'row':0,'col':0},
            'random_range':{'row':.2,'col':.2},'samples':[{'axis':'row','value':.5},{'axis':'row','value':.5}]},
            rule_id='rule/review_spawn')
    assert not sim.session.random.samples


def movement_model(mode='WALK'):
    data=model({'row':0,'col':0});data['scenarioDraft']['map']=tiles(4,4)
    wave=data['scenarioDraft']['waves'][0];wave['position']={'row':0,'col':0}
    wave['route']={'motionMode':mode,'allowDiagonalMove':True,'startPosition':wave['position'],
        'endPosition':{'row':3,'col':3},'checkpoints':[{'type':'MOVE','position':{'row':1,'col':1}},
            {'type':'WAIT_FOR_SECONDS','time':.2},{'type':'MOVE','position':{'row':2,'col':2}}]}
    data['rules'].append({'id':'rule/review_diagonal','kind':'calculation_rule','extends':'rule/ark_movement_path',
        'parameters':{'use_route_diagonal':True,'corner_cut':False}})
    data['scenarioDraft']['rules']={'movement.path':'rule/review_diagonal'}
    return data


def test_diagonal_routing_preserves_wait_checkpoint_in_actual_movement():
    sim=engine(movement_model());sim.advance(44)
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':1}
    sim.advance(4)
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':1}
    sim.advance(5)
    p=sim.ctx.get('born',('spatial','position'));assert p['row']>1 and p['col']>1


def test_fly_is_straight_through_walls_under_eight_neighbor_profile():
    data=movement_model('FLY');data['scenarioDraft']['map']=tiles(4,4,{(0,1),(1,0),(1,1)})
    data['scenarioDraft']['waves'][0]['route']['checkpoints']=[]
    sim=engine(data);sim.advance(31)
    p=sim.ctx.get('born',('spatial','position'))
    assert p['row']==pytest.approx(31/(30*math.sqrt(2))) and p['col']==p['row']
    assert sim.ctx.get('born',('spatial','movement_path'))==[{'row':3,'col':3}]


def steering_model():
    data=model({'row':0,'col':0});data['scenarioDraft']['map']=tiles(3,5)
    wave=data['scenarioDraft']['waves'][0];wave['position']={'row':1,'col':0}
    wave['route']={'motionMode':'WALK','allowDiagonalMove':True,'startPosition':wave['position'],
        'endPosition':{'row':1,'col':4},'checkpoints':[]}
    data['entities'][0]['components']['spatial']['steering']={'rule':'rule/review_steer',
        'parameters':{'response_factor':8,'max_acceleration':10}}
    data['rules'].append({'id':'rule/review_steer','kind':'calculation_rule','contract':'movement.steering',
        'implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}})
    return data


def steer(sim,**updates):
    request={'origin':{'row':0,'col':0},'destination':{'row':0,'col':10},
        'velocity':{'row':0,'col':0},'speed':2,'delta_seconds':.25,
        'parameters':{'response_factor':4,'max_acceleration':1}}
    request.update(updates)
    return sim.ctx.calc('movement.steering',request,rule_id='rule/review_steer')


def test_steering_start_acceleration_bound_and_turn_retains_inertia():
    sim=engine(steering_model());first=steer(sim)
    assert first['velocity']=={'row':0,'col':.25}
    assert first['position']=={'row':0,'col':.0625}
    turn=steer(sim,destination={'row':10,'col':0},velocity={'row':0,'col':.25})
    assert turn['velocity']['row']==pytest.approx(2/math.sqrt(65))
    assert turn['velocity']['col']==pytest.approx(.25-.25/math.sqrt(65))
    assert math.hypot(turn['velocity']['row'],turn['velocity']['col']-.25)==pytest.approx(.25)
    assert turn['position']['row']>0 and turn['position']['col']>0


@pytest.mark.parametrize('velocity,expected',[({'row':-1,'col':0},{'row':-1/30,'col':0}),
    ({'row':0,'col':-1},{'row':0,'col':-1/30})])
def test_zero_acceleration_cannot_snap_sideways_or_backwards_to_nearby_goal(velocity,expected):
    sim=engine(steering_model())
    result=steer(sim,destination={'row':0,'col':.01},velocity=velocity,
        speed=1,delta_seconds=1/30,parameters={'response_factor':0,'max_acceleration':0})
    assert result['velocity']==velocity
    assert result['position']==pytest.approx(expected)


def test_forward_step_crossing_goal_clamps_to_current_waypoint():
    sim=engine(steering_model())
    result=steer(sim,destination={'row':0,'col':.01},velocity={'row':0,'col':1},
        speed=1,delta_seconds=1/30,parameters={'response_factor':0,'max_acceleration':0})
    assert result['position']=={'row':0,'col':.01}
    assert result['velocity']=={'row':0,'col':1}


def test_declared_arrival_radius_requires_actual_toward_segment_and_is_observable():
    sim=engine(steering_model())
    params={'response_factor':0,'max_acceleration':0,'arrival_radius':.05}
    sideways=steer(sim,destination={'row':0,'col':.01},velocity={'row':-1,'col':0},
        speed=1,delta_seconds=1/30,parameters=params)
    assert sideways['position']=={'row':pytest.approx(-1/30),'col':0}
    assert sideways['arrival_captured'] is False
    towards=steer(sim,destination={'row':0,'col':.06},velocity={'row':0,'col':1},
        speed=1,delta_seconds=1/30,parameters=params)
    assert towards['position']=={'row':0,'col':.06}
    assert towards['arrival_captured'] is True


def test_invalid_arrival_radius_is_rejected_instead_of_becoming_hidden_capture():
    sim=engine(steering_model())
    with pytest.raises(ValueError):steer(sim,parameters={'response_factor':8,'max_acceleration':10,'arrival_radius':-.1})


def test_live_steering_uses_source_rule_and_collision_clears_velocity():
    data=steering_model();data['scenarioDraft']['map']=tiles(3,5,{(1,1)})
    # An explicit replacement attempts a straight jump through the wall;
    # core must clip accepted point movement rather than trust its endpoint.
    data['rules'][-1]['implementation']={'type':'expression','expression':
        "{'position':{'row':inputs.origin.row,'col':inputs.origin.col+2},'velocity':{'row':0,'col':60}}"}
    sim=engine(data);sim.advance(1)
    p=sim.ctx.get('born',('spatial','position'))
    assert p['row']==1 and p['col']==pytest.approx(.5) and p['col']<.5
    assert sim.ctx.get('born',('spatial','velocity'))=={'row':0,'col':0}


def test_replacement_rule_respects_declared_waypoint_and_wait_clears_velocity():
    data=steering_model();route=data['scenarioDraft']['waves'][0]['route']
    route['checkpoints']=[{'type':'MOVE','position':{'row':1,'col':1}},
        {'type':'WAIT_FOR_SECONDS','time':.2},{'type':'MOVE','position':{'row':1,'col':2}}]
    data['rules'][-1]['implementation']={'type':'expression','expression':
        "{'position':inputs.destination,'velocity':{'row':0,'col':1}}"}
    sim=engine(data);sim.advance(1)
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':1}
    sim.advance(2)
    assert sim.ctx.get('born',('spatial','velocity'))=={'row':0,'col':0}
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':1}
    sim.advance(4)
    assert sim.ctx.get('born',('spatial','position'))=={'row':1,'col':1}
    sim.advance(3)
    assert sim.ctx.get('born',('spatial','position'))['col']>=2


def test_ground_blocking_stops_motion_and_clears_steering_velocity():
    data=steering_model()
    data['entities'].append({'id':'unit/review_blocker','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'max_hp':100,'block_count':1}},'spatial':{},
            'deployable':{'terrain':'ground'},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}}}})
    data['scenarioDraft']['initialEntities']=[{'definition':'unit/review_blocker','instanceAlias':'blocker',
        'position':{'row':1,'col':1}}]
    sim=engine(data);sim.advance(1)
    assert sim.ctx.spatial.blocked_by('born')==sim.session.world.resolve('blocker')
    p=sim.ctx.get('born',('spatial','position'));sim.advance(3)
    assert sim.ctx.get('born',('spatial','position'))==p
    assert sim.ctx.get('born',('spatial','velocity'))=={'row':0,'col':0}


def test_spawn_diagonal_steering_wait_checkpoint_and_full_replay_match():
    data=movement_model();data['entities'][0]['components']['spatial']['steering']={
        'rule':'rule/review_steer','parameters':{'response_factor':8,'max_acceleration':10}}
    data['rules'].append({'id':'rule/review_steer','kind':'calculation_rule','contract':'movement.steering',
        'implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}})
    data['scenarioDraft']['waves'][0]['placement']['random_range']={'row':.1,'col':.1}
    program=Compiler().compile(data);sim=Engine.create(program,seed=703);sim.advance(35)
    restored=Engine.restore(program,sim.checkpoint());sim.advance(100);restored.advance(100)
    assert first_difference(sim.snapshot(),restored.snapshot()) is None
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
    assert len(sim.session.random.samples)==2
