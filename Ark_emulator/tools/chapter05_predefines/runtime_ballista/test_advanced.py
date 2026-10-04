"""Effective state, ray ordering, movement, lifecycle and source-clock boundaries."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from test_consumer_v2 import fixture,make,events,Compiler,Engine
def test_invalid_nearer_target_is_skipped_then_real_far_target_gets_only_quota():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'target_free':True}};s=Engine.create(Compiler().compile(p));s.advance(220);damage=events(s,'damage.accepted');assert len(damage)==1 and damage[0]['payload']['target']==s.session.world.resolve('far');assert s.ctx.resources.current('first','hp')==5000
def test_live_buff_camouflage_added_after_launch_is_projected_before_collision():
 p=fixture();p['buffs']=[{'id':'buff/ballista_test/camo','kind':'buff','selection_flags':{'abnormal_flags':[17]}}];p['entities'][1]['dependencies']=['buff/ballista_test/camo'];s=Engine.create(Compiler().compile(p));s.advance(159);s.ctx.buffs.apply('first','first','buff/ballista_test/camo');s.advance(61);damage=events(s,'damage.accepted');assert len(damage)==1 and damage[0]['payload']['target']==s.session.world.resolve('far')
def test_raw_motion3_allows_real_flying_combat_player():
 p=fixture(second=False);p['entities'][1]['components']['selection_state']['motion']=2;s=Engine.create(Compiler().compile(p));s.advance(220);assert events(s,'damage.accepted')[0]['payload']['target']==s.session.world.resolve('first')
def test_enemy_side_and_category4_device_are_not_player_combat_targets():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'side':1,'category':4}};s=Engine.create(Compiler().compile(p));s.advance(220);assert events(s,'damage.accepted')[0]['payload']['target']==s.session.world.resolve('far')
def test_relative_sweep_catches_real_crossing_target_between_step_endpoints():
 p=fixture(second=False);p['scenarioDraft']['initialEntities'][1]['position']={'row':0,'col':1};s=Engine.create(Compiler().compile(p));s.advance(159);s.ctx.set('first',('spatial','position'),{'row':2,'col':1});s.advance(20);assert events(s,'damage.accepted')[0]['payload']['target']==s.session.world.resolve('first')
def test_inflight_projectile_really_retains_after_source_retired_and_tile_layer_cleans():
 s=make();s.advance(159);s.ctx.lifecycle.retire('caster','withdrawn');s.advance(61);damage=events(s,'damage.accepted');assert len(damage)==1 and damage[0]['payload']['target']==s.session.world.resolve('first');assert s.ctx.spatial.grid.tile(1,0)['passableMask']==3
def test_repeat_shots_are_real_SP_payments_with_cast_freeze_not_constant_external_schedule():
 s=make();s.advance(530);casts=[e for e in events(s,'ability.started') if e['payload']['ability']=='ability/ballista/source_shot'];launched=events(s,'projectile.launched');assert len(casts)==len(launched)==3;assert all(b['time']-a['time']==6 for a,b in zip(casts,launched));assert all(b['time']-a['time']>=155 for a,b in zip(casts,casts[1:]));payments=[e for e in events(s,'resource.changed') if e['payload'].get('ability')=='ability/ballista/source_shot' and e['payload'].get('reason')=='ability_cost'];assert len(payments)==3 and all(e['payload']['delta']==-5 for e in payments);assert not s.export_replay()['commands']
