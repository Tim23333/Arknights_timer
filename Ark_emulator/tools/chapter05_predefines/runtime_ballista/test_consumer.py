"""Actual source device fires automatically, hits real qualified actors, owns tile layer."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MODULE=ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.reference.json'
def fixture(second=True,hidden=False,free=False,camouflage=False):
 p=json.loads(MODULE.read_bytes());target={'id':'unit/ballista_test_target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':5000,'atk':0,'def':100,'mres':0,'move_speed':0,'block_count':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1,'target_free':free,'camouflage':camouflage},'spatial':{'radius':.1},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(target);initial=[{'definition':p['entities'][0]['id'],'instanceAlias':'caster','position':{'row':1,'col':0},'facing':'right'},{'definition':target['id'],'instanceAlias':'first','position':{'row':1,'col':3}}]
 if hidden:initial[0].update(active=False,registration_key='ballista_dormant_source')
 if second:initial.append({'definition':target['id'],'instanceAlias':'far','position':{'row':1,'col':6}})
 p['scenarioDraft']={'id':'scene/actual_ballista_source_test','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':9},'seed':507006,'objectives':{},'initialEntities':initial};return p
def make(**kwargs):return Engine.create(Compiler().compile(fixture(**kwargs)))
def events(s,kind):return [thaw(e) for e in s.session.events if e['type']==kind]
def test_actual_SP5_source_actor_fires_no_external_schedule_first_hit_only_600minus100():
 s=make();s.advance(220);casts=[e for e in events(s,'ability.started') if e['payload']['ability']=='ability/ballista/source_shot'];assert len(casts)==1
 shots=events(s,'projectile.launched');hits=events(s,'projectile.hit');damage=events(s,'damage.accepted');assert len(shots)==len(hits)==len(damage)==1 and damage[0]['payload']['target']==s.session.world.resolve('first') and damage[0]['payload']['amount']==500
 assert shots[0]['time']-casts[0]['time']==6;assert s.ctx.resources.current('far','hp')==5000 and s.ctx.resources.current('first','hp')==4500
 assert hits[0]['payload']['source']==s.session.world.resolve('caster') and s.session.world.resolve('caster')==shots[0]['payload']['target'];assert not [e for e in s.session.world.entities() if 'dummy' in e['definition_id']]
def test_no_combat_target_still_fires_to_source_direction_and_map_bound_no_dummy_or_self_hit():
 p=fixture(second=False);p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];s=Engine.create(Compiler().compile(p));s.advance(220);assert len(events(s,'projectile.launched'))==1 and not events(s,'damage.accepted');assert s.ctx.resources.current('caster','hp')==100
 invalid=events(s,'projectile.invalid');assert invalid and invalid[-1]['payload']['reason']=='reached';assert invalid[-1]['payload']['position']['col']==8.5
@pytest.mark.parametrize('name',['target_free','camouflage'])
def test_actual_target_free_and_camouflage_do_not_consume_quota(name):
 s=make(free=name=='target_free',camouflage=name=='camouflage');s.advance(220);assert not events(s,'damage.accepted')
def test_source_walls_are_passed_without_actor_virtualization():
 p=fixture();tiles=[{'tileKey':'tile_road','buildableType':1,'passableMask':3} for _ in range(27)];tiles[11]={'tileKey':'tile_wall','buildableType':2,'passableMask':2};p['scenarioDraft']['map']['tiles']=tiles;s=Engine.create(Compiler().compile(p));s.advance(220);assert events(s,'damage.accepted')[0]['payload']['target']==s.session.world.resolve('first')
def test_native_trapmode_owned_overlay_exact_and_retirement_restores_base():
 s=make();tile=s.ctx.spatial.grid.tile(1,0);assert tile['buildableType']==0 and tile['passableMask']==2 and tile['physicalHeight']==pytest.approx(.4000000059604645);s.ctx.lifecycle.retire('caster','withdrawn');tile=s.ctx.spatial.grid.tile(1,0);assert tile['buildableType']!=0 and tile['passableMask']==3
def test_real_dormant_activation_has_no_early_layer_SP_or_projectiles_then_live_shot():
 s=make(hidden=True);s.advance(200);assert not events(s,'projectile.launched') and s.ctx.resources.current('caster','sp')==0 and s.ctx.spatial.grid.tile(1,0)['buildableType']!=0;s.ctx.lifecycle.activate('ballista_dormant_source');s.advance(220);assert len(events(s,'projectile.launched'))==1 and events(s,'damage.accepted');assert s.ctx.spatial.grid.tile(1,0)['buildableType']==0
def test_public_ordered_midflight_checkpoint_and_start_replay_equal(tmp_path):
 s=make();s.advance(159);h=write_ordered(tmp_path/'midflight.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'midflight.json',h));s.advance(70);r.advance(70);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_source_facing_is_captured_per_launch_not_later_retargeted():
 s=make();s.advance(159);s.ctx.set('caster',('spatial','facing'),'left');s.advance(61);assert events(s,'damage.accepted')[0]['payload']['target']==s.session.world.resolve('first')
