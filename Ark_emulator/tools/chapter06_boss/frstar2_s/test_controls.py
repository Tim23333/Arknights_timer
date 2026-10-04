"""Public skill eligibility, cast qualification and timing controls."""
import pytest
from ark_sim import Compiler,Engine
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.frstar2_s.test_module import package,deploy,events,flags
from tools.chapter06_boss.frstar2_s.build_module import COLD,I,B
def make(p):return Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6217,providers=providers())
def controller(p,ability):
 p['entities'].append({'id':'unit/test/story/controller','kind':'entity','components':{'attributes':{'base':{'max_hp':100,'atk':1}},'resources':{'hp':{'role':'health','initial':100,'capacity':100}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[ability]}})
 p['scenarioDraft']['initialEntities'].append({'definition':'unit/test/story/controller','instanceAlias':'controller','position':{'row':4,'col':8}})
def test_pre_gap_actual_frozen_target_owned_multiplier_before_cold_and_fixed_skill_time():
 p=package(False);controller(p,'ability/ch6/cold/apply5');s=make(p);deploy(s)
 for tick in (479,480):s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=tick)
 s.session.advance(568);assert 16 in flags(s,'player')
 packets=[e for e in events(s,'damage.accepted') if e['payload']['source']==s.session.world.resolve('boss')]
 assert [(e['time'],e['payload']['amount']) for e in packets]==[(567,1800)]
@pytest.mark.parametrize('motion',[1,2])
def test_pre_gap_native_burst_target_motion3_includes_ground_and_air(motion):
 p=package(False);p['entities'][1]['components']['selection_state']['motion']=motion
 s=make(p);deploy(s);s.session.advance(568)
 assert any(e['time']==567 and e['payload']['amount']==900 for e in events(s,'damage.accepted'))
def test_pre_gap_invalid_target_no_burst_and_no_normal_fallback():
 p=package(False);p['entities'][1]['components']['selection_state']['category']=2
 s=make(p);deploy(s);s.session.advance(650)
 assert not [e for e in events(s,'ability.started') if e['payload']['ability']==B]
 assert not events(s,'damage.accepted') and not events(s,'projectile.launched')
def test_pre_gap_controlled_same_ready_shield_priority_then_full_busy():
 p=package(False)
 for a in p['abilities']+p['definitions']:
  if a.get('id') in [I,B]:a['initial_cooldown_seconds']=0
 s=make(p);deploy(s);s.session.advance(1)
 assert [(e['time'],e['payload']['ability'],e['payload']['priority']) for e in events(s,'ability.arbitrated')]==[(0,I,2)]
 s.session.advance(89);assert len(events(s,'ability.arbitrated'))==1
 s.session.advance(2);assert events(s,'ability.arbitrated')[1]['payload']['ability']==B
