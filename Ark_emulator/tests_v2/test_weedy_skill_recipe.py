"""Selected S3: real splash, force ledger, distance damage and owned cannon."""
from copy import deepcopy

import pytest

from ark_sim import Compiler,Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_weedy_skill_recipe import (ROOT,OUTPUT,read,build,SKILL,DEPLOY,TOKEN_SKILL,RUPTURE,HOST,TOKEN)


@pytest.fixture(scope='module')
def package():return read(OUTPUT)


def engine(data,charged=True):
    data=deepcopy(data)
    if charged:data['entities'][0]['components']['resources']['sp']['initial']=33
    return Engine.create(Compiler().compile(data),seed=202)


def cast(sim):sim.submit({'action':'activate_ability','source':'weedy','ability':SKILL})


def events(sim,kind,ability=None):
    return [e for e in sim.session.events if e['type']==kind and (ability is None or e['payload'].get('ability')==ability)]


def tokens(sim):return [e for e in sim.session.world.entities() if 'weedy_cannon' in e['tags']]


def true_total(sim):return sum(e['payload']['amount'] for e in events(sim,'damage.accepted') if e['payload'].get('ability') is None)


def test_builder_and_native_profile_boundaries(package):
    assert build()==package
    assert package['status']=='selected_skill_model_partial'
    metadata=package['manifest']['metadata']
    assert metadata['push_profile']['native_curve_verified'] is False
    assert metadata['token_growth_profile']['model_stats']['atk']==561
    assert package['entities'][0]['components']['attributes']['base']['atk']==693
    assert metadata['native_skills']['skchr_weedy_3']['attack_fields']['_waitForProjectileInvalid']==1
    with pytest.raises(ValueError,match='complete native Weedy unsupported'):build(require_complete=True)
    Compiler().compile(package)


def test_actual_sp_payment_and_freeze_only_until_projectile_invalid(package):
    sim=engine(package,charged=False);cast(sim);sim.advance(1)
    assert events(sim,'command.rejected') and sim.ctx.resources.current('weedy','sp')==20
    sim.advance(389)
    assert sim.ctx.resources.current('weedy','sp')==33
    cast(sim);sim.advance(18)
    assert sim.ctx.resources.current('weedy','sp')==0
    assert not events(sim,'damage.accepted',SKILL)
    sim.advance(1)
    assert [(e['time'],e['payload']['amount']) for e in events(sim,'damage.accepted',SKILL)]==[(408,pytest.approx(1940.4))]
    sim.advance(31)
    assert sim.ctx.resources.current('weedy','sp')==1
    assert sim.ctx.get('enemy',('buffs','instances'))  # Rupture is still active; it did not freeze caster8s.


def test_single_projectile_actual_impact_splash_not_one_bullet_per_enemy(package):
    data=deepcopy(package)
    for alias,col in [('near',5),('outside',6)]:
        data['scenarioDraft']['initialEntities'].append({'definition':data['entities'][2]['id'],'instanceAlias':alias,'position':{'row':3,'col':col}})
    sim=engine(data);cast(sim);sim.advance(19)
    assert len(events(sim,'projectile.launched',SKILL))==1
    hits=events(sim,'damage.accepted',SKILL)
    assert len(hits)==2 and {e['payload']['target'] for e in hits}=={sim.session.world.resolve('enemy'),sim.session.world.resolve('near')}
    assert all(e['payload']['amount']==pytest.approx(1940.4) for e in hits)
    assert sim.ctx.resources.current('outside','hp')==1000000
    assert len(events(sim,'attack.accepted',SKILL))==1


def test_profile_weight_changes_force_and_actual_ledger_drives_true_damage(package):
    sim=engine(package);cast(sim);sim.advance(65)
    position=sim.ctx.get('enemy',('spatial','position'))
    assert position['col']==pytest.approx(7.33058)
    distance=position['col']-4
    assert sim.ctx.get('enemy',('spatial','distance_travelled'))==pytest.approx(distance)
    assert true_total(sim)==pytest.approx(distance*1200)
    heavy=deepcopy(package);heavy['entities'][2]['components']['attributes']['base']['mass_level']=3
    sim=engine(heavy);cast(sim);sim.advance(65)
    assert sim.ctx.get('enemy',('spatial','position'))['col']==pytest.approx(5.56247)
    assert true_total(sim)==pytest.approx(1.56247*1200)


def test_zero_push_and_stationary_target_have_no_distance_damage(package):
    data=deepcopy(package);data['entities'][2]['components']['attributes']['base']['mass_level']=6
    sim=engine(data);cast(sim);sim.advance(100)
    assert sim.ctx.get('enemy',('spatial','position'))=={'row':3,'col':4}
    assert true_total(sim)==0
    assert not events(sim,'movement.traveled')


def test_obstacle_clips_actual_movement_and_never_charges_nominal_full_push(package):
    data=deepcopy(package);tiles=[{'tileKey':'tile_floor','passableMask':1,'buildableType':1} for _ in range(7*18)]
    tiles[3*18+5]={'tileKey':'tile_wall','passableMask':0,'buildableType':0};data['scenarioDraft']['map']['tiles']=tiles
    sim=engine(data);cast(sim);sim.advance(80)
    actual=sim.ctx.get('enemy',('spatial','distance_travelled'),0)
    assert 0<actual<1
    assert sim.ctx.get('enemy',('spatial','position'))['col']<4.5
    assert true_total(sim)==pytest.approx(actual*1200)
    assert true_total(sim)<3.33058*1200


def test_back_and_forth_counts_actual_path_not_net_displacement_and_removal_flushes_tail(package):
    sim=engine(package)
    sim.ctx.buffs.apply('weedy','enemy',RUPTURE)
    sim.ctx.movement.displace('weedy','enemy',{'offset':{'row':0,'col':0.5}},None)
    sim.ctx.movement.displace('weedy','enemy',{'offset':{'row':0,'col':-0.5}},None)
    assert sim.ctx.get('enemy',('spatial','position'))=={'row':3,'col':4}
    sim.ctx.buffs.remove('enemy',RUPTURE)
    assert true_total(sim)==pytest.approx(1200)
    assert sim.ctx.resources.current('enemy','hp')==pytest.approx(998800)


def test_natural_walking_is_measured_only_after_lease_start(package):
    data=deepcopy(package);data['entities'][2]['components']['attributes']['base']['move_speed']=0.3
    data['scenarioDraft']['initialEntities'][1]['route']={'motionMode':'WALK','endPosition':{'row':3,'col':16}}
    sim=engine(data);sim.advance(10)
    start=sim.ctx.get('enemy',('spatial','distance_travelled'))
    sim.ctx.buffs.apply('weedy','enemy',RUPTURE);sim.advance(60);sim.ctx.buffs.remove('enemy',RUPTURE)
    actual=sim.ctx.get('enemy',('spatial','distance_travelled'))-start
    assert actual==pytest.approx(0.6)
    assert true_total(sim)==pytest.approx(actual*1200)


def test_owned_deployment_battle_dp_and_capacity_failure_are_atomic(package):
    sim=engine(package);sim.ctx.abilities.start('weedy',DEPLOY)
    assert sim.ctx.resources.current('system/battle','dp')==15 and len(tokens(sim))==1
    sim.advance(1)  # Finish the zero-duration deploy cast before probing owned capacity.
    before=sim.checkpoint()
    with pytest.raises(ValueError,match='capacity'):sim.ctx.abilities.start('weedy',DEPLOY)
    assert first_difference(before,sim.checkpoint()) is None
    assert tokens(sim)[0]['components']['ownership']['owner']==sim.session.world.resolve('weedy')
    data=deepcopy(package);data['scenarioDraft']['resources']['dp']['initial']=4
    sim=engine(data);before=sim.checkpoint()
    with pytest.raises(ValueError,match='insufficient'):sim.ctx.abilities.start('weedy',DEPLOY)
    assert first_difference(before,sim.checkpoint()) is None and not tokens(sim)


def test_cannon_linked_s3_uses_own_atk_cost_zero_force_plus_one_and_single_extended_rupture(package):
    data=deepcopy(package);data['entities'][2]['components']['attributes']['base']['mass_level']=3
    sim=engine(data);sim.ctx.abilities.start('weedy',DEPLOY);sim.advance(1);cast(sim);sim.advance(65)
    token_hits=events(sim,'damage.accepted',TOKEN_SKILL)
    assert len(token_hits)==1 and token_hits[0]['payload']['amount']==pytest.approx(1570.8)
    assert len(events(sim,'damage.accepted',SKILL))==1
    plans=events(sim,'movement.push_started')
    assert [e['payload']['plan']['distance'] for e in plans]==pytest.approx([1.98705,1.56247])
    rupture=[b for b in sim.ctx.get('enemy',('buffs','instances')) if b['definition']==RUPTURE]
    assert len(rupture)==1 and rupture[0]['stacks']==1
    assert rupture[0]['expires_at']==token_hits[0]['time']+480
    actual=sim.ctx.get('enemy',('spatial','distance_travelled'))
    assert true_total(sim)==pytest.approx(actual*1200)  # Never double2400/tile.


def test_wrong_owner_or_outside_manhattan_four_cannon_cannot_be_linked(package):
    sim=engine(package);sim.ctx.abilities.start('weedy',DEPLOY);sim.advance(1)
    cannon=tokens(sim)[0]['id'];sim.ctx.movement.displace('weedy',cannon,{'position':{'row':3,'col':7}},None)
    cast(sim);sim.advance(80)
    assert not events(sim,'damage.accepted',TOKEN_SKILL)
    assert len(events(sim,'damage.accepted',SKILL))==1
    sim=engine(package);sim.ctx.lifecycle.create(TOKEN,{'row':3,'col':3},owner=sim.session.world.resolve('enemy'))
    cast(sim);sim.advance(80)
    assert not events(sim,'damage.accepted',TOKEN_SKILL)


def test_nearby_cannon_sp_period_and_lifetime_or_owner_retire_cleanups(package):
    sim=engine(package,charged=False);sim.ctx.abilities.start('weedy',DEPLOY);sim.advance(91)
    assert sim.ctx.resources.current('weedy','sp')==24  # time3 + cannon1.
    cannon=tokens(sim)[0]['id'];sim.ctx.movement.displace('weedy',cannon,{'position':{'row':3,'col':7}},None)
    sim.advance(90);assert sim.ctx.resources.current('weedy','sp')==27  # No outsidecannon grant.
    sim.advance(420);assert not sim.ctx.alive(cannon)
    sim=engine(package);sim.ctx.abilities.start('weedy',DEPLOY);cannon=tokens(sim)[0]['id']
    sim.ctx.lifecycle.retire('weedy','withdrawn')
    assert not sim.ctx.alive(cannon)


def test_cannon_external_sp_grant_respects_projectile_cast_freeze(package):
    data=deepcopy(package);data['entities'][2]['components']['attributes']['base']['mass_level']=9
    sim=engine(data);sim.submit({'action':'activate_ability','source':'weedy','ability':DEPLOY},at=0)
    sim.submit({'action':'activate_ability','source':'weedy','ability':SKILL},at=80)
    sim.advance(95)
    assert sim.ctx.resources.current('weedy','sp')==0
    suppressed=events(sim,'resource.recovery_suppressed')
    assert any(e['time']==90 and e['payload']['resource']=='sp' for e in suppressed)
    assert not events(sim,'ability.finished',SKILL)
    sim.advance(8)
    assert events(sim,'ability.finished',SKILL)


def test_repeated_rupture_hit_flushes_tail_and_never_recounts_old_cursor(package):
    sim=engine(package)
    sim.ctx.buffs.apply('weedy','enemy',RUPTURE)
    sim.ctx.movement.displace('weedy','enemy',{'offset':{'row':0,'col':0.25}},None)
    sim.ctx.buffs.apply('weedy','enemy',RUPTURE)
    assert true_total(sim)==pytest.approx(300)
    active=next(b for b in sim.ctx.get('enemy',('buffs','instances')) if b['definition']==RUPTURE)
    assert active['expires_at']==480 and active['stacks']==1
    sim.ctx.movement.displace('weedy','enemy',{'offset':{'row':0,'col':0.25}},None)
    sim.ctx.buffs.remove('enemy',RUPTURE)
    assert true_total(sim)==pytest.approx(600)


def test_weedy_ledger_cannon_callbacks_checkpoint_and_replay_are_identical(package):
    sim=engine(package);sim.submit({'action':'activate_ability','source':'weedy','ability':DEPLOY},at=0)
    cast_command={'action':'activate_ability','source':'weedy','ability':SKILL};sim.submit(cast_command,at=1)
    sim.advance(33);checkpoint=sim.checkpoint();sim.advance(470);expected=sim.snapshot()
    restored=Engine.restore(sim.program,checkpoint);restored.advance(470)
    assert first_difference(expected,restored.snapshot()) is None
    assert first_difference(expected,replay(sim.program,sim.export_replay()).snapshot()) is None
