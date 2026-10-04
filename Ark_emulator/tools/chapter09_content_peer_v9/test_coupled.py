"""Independent pair numerical/source/first-last cases on v9 frozen module."""
from tools.chapter09_content_peer_v9.fixture import *
from tools.chapter09_content_peer_v9.test_payload import create,events,proof
from ark_sim.domains.selection import DEFAULT_STATE
import pytest

@pytest.mark.parametrize('paired,expected_cycle,expected_speed',[(False,2.1,1.3),(True,.9,1.0)])
def test_exact_native_pair_controls_trait_cycle_and_player_ASPD(paired,expected_cycle,expected_speed):
 p=coupled_scene(holy_positions=((3,3),),shadow_positions=((3,3.6),) if paired else ((0,7),),player=(2.2,3));s=proof(p,'coupled_traits_'+str(paired),1,4);assert s.ctx.attributes.value('shadow0','attack_interval')==pytest.approx(expected_cycle);assert s.ctx.attributes.value('observer','attack_speed_ratio')==pytest.approx(expected_speed);assert s.ctx.attributes.value('holy0','mres')==70;assert s.ctx.attributes.value('shadow0','mres')==0

@pytest.mark.parametrize('paired,times',[(False,[18]),(True,[9,36,63])])
def test_actual_cast_time_source_hit_sampling_and_RES43_damage(paired,times):
 s=proof(coupled_blocked_scene(paired),'coupled_hits_'+str(paired),8,66);assert not events(s,'command.rejected');hits=events(s,'damage.accepted');assert [t for t,_ in hits]==times;assert [x['amount'] for _,x in hits]==[228]*len(times)

def test_partner_loss_mid_windup_preserves_first_hit_and_next_clock_sample():
 s=proof(coupled_blocked_scene(True,leave_at=2),'coupled_midcast_loss',3,66);assert not events(s,'command.rejected');assert [t for t,_ in events(s,'damage.accepted')]==[9,45];assert s.ctx.attributes.value('shadow0','attack_interval')==2.1

def test_multisource_first_acquisition_last_release_is_not_additive():
 p=coupled_scene(holy_positions=((3,3),(3,4)),shadow_positions=((3,3.5),),player=(2.2,3.5));holy=next(e for e in p['entities'] if '/duholy/' in e['id']);holy['components']['abilities'].append('ability/peer/holy_retire');p['abilities'].append({'id':'ability/peer/holy_retire','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}}]});p['scenarioDraft']['commands']=[{'at':2,'action':'skill','source':'holy0','ability':'ability/peer/holy_retire'},{'at':4,'action':'skill','source':'holy1','ability':'ability/peer/holy_retire'}]
 s=create(p);s.advance(1);trigger=[b for b in s.ctx.get('shadow0',('buffs','instances')) if b['definition']=='buff/ch9/coupled/dushdo/trigger'];assert len(trigger)==1 and len(trigger[0]['aura_leases'])==2;assert s.ctx.attributes.value('shadow0','attack_interval')==pytest.approx(.9);assert s.ctx.attributes.value('observer','attack_speed_ratio')==1.0
 s.advance(2);trigger=[b for b in s.ctx.get('shadow0',('buffs','instances')) if b['definition']=='buff/ch9/coupled/dushdo/trigger'];assert len(trigger)==1 and len(trigger[0]['aura_leases'])==1;assert trigger[0]['source']==s.session.world.resolve('holy1');assert s.ctx.attributes.value('shadow0','attack_interval')==pytest.approx(.9)
 s=proof(p,'coupled_first_last',3,7);assert not events(s,'command.rejected');assert s.ctx.attributes.value('shadow0','attack_interval')==2.1;assert s.ctx.attributes.value('observer','attack_speed_ratio')==1.3;shadow=s.session.world.resolve('shadow0');assert len([x for _,x in events(s,'coupled.trait.started') if x['target']==shadow])==1;assert len([x for _,x in events(s,'coupled.trait.finished') if x['target']==shadow])==1

@pytest.mark.parametrize('profile,speed',[('native_collider',1.3),('trait_blackboard',1.0)])
def test_native_radius1_vs_explicit_BB1point1_reference_profile(profile,speed):
 p=coupled_scene(holy_positions=((3,3),),shadow_positions=((3,3.5),),player=(3,4.05));meta=json.loads(COUPLED.read_bytes())['manifest']['metadata'];assert meta['reference_profiles']['radius']=='native_collider'
 if profile=='trait_blackboard':
  source=meta['native_closures']['enemy_1174_duholy']['variant']['native_enemy']['resolved']['talentBlackboard'];bb={x['key']:x['value'] for x in source};assert bb['traitAbility.range_radius']==1.1;next(s for s in p['selectors'] if s['id']=='selector/ch9/coupled/duholy/players')['region']['radius']=bb['traitAbility.range_radius'];p['manifest']['metadata']={'explicit_reference_profile':'trait_blackboard','source':'source BB traitAbility.range_radius1.1, preserves nativeCollider1 as separate default'}
 s=proof(p,'coupled_radius_'+profile,1,4);assert s.ctx.attributes.value('observer','attack_speed_ratio')==speed

def test_invisible_initial_then_blocked_release_exact_three_second_deadline():
 p=coupled_blocked_scene(False,unblock_at=2);s=create(p);s.advance(4);owner=next(b for b in s.ctx.get('shadow0',('buffs','instances')) if b['definition']=='buff/ch9/coupled/dushdo/invisible_owner');assert owner['toggle_state']['restore_at']==93;assert owner['toggle_state']['held'] is False
 s=proof(p,'coupled_invisible_restore',92,95);applied=[t for t,x in events(s,'buff.applied') if x['buff']=='buff/ch9/coupled/dushdo/invisible'];removed=[t for t,x in events(s,'buff.removed') if x['buff']=='buff/ch9/coupled/dushdo/invisible'];assert applied==[0,93];assert removed==[0];assert s.ctx.spatial.selection_state('shadow0',DEFAULT_STATE)['invisible']


def test_duholy_refraction70_silence_and_dushdo_unused_BB_no_refraction():
 p=coupled_scene();controller=actor('silencer',0);controller['components']['abilities']=['ability/peer/silence_holy'];p['entities'].append(controller);p['buffs'].append({'id':'buff/peer/silence','kind':'buff','duration_seconds':2/30,'selection_flags':{'abnormal_flags':[12]}});p['selectors'].append({'id':'selector/peer/holy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'].append({'id':'ability/peer/silence_holy','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/holy','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/peer/silence'}}]});p['scenarioDraft']['initialEntities'].append({'definition':controller['id'],'instanceAlias':'silencer','position':{'row':0,'col':0}});p['scenarioDraft']['commands']=[{'at':1,'action':'skill','source':'silencer','ability':'ability/peer/silence_holy'}]
 s=create(p);s.advance(2);assert not events(s,'command.rejected');assert s.ctx.attributes.value('holy0','mres')==0;assert s.ctx.attributes.value('shadow0','mres')==0;s=proof(p,'coupled_silence',2,5);assert s.ctx.attributes.value('holy0','mres')==70;assert s.ctx.attributes.value('shadow0','mres')==0

def test_DB_Flame_has_no_owned_native_skill_and_requested_IR_is_rejected():
 p=coupled_scene();m=json.loads(COUPLED.read_bytes())['manifest']['metadata'];unused=m['unused_db_rows']['enemy_1174_duholy'];assert unused['rows'][0]['prefabKey']=='Flame';native=m['native_closures']['enemy_1174_duholy'];root=next(c for c in native['prefab']['components'].values() if c['native_class']=='Enemy');assert root['raw']['_commonAbilities']==[];assert native['owned_native_skill_components']==[];assert native['variant']['modes'][0]['raw']['_generalAbilities']==[];assert not any('Flame' in a['id'] for a in p['abilities'])
 p['scenarioDraft']['commands']=[{'at':0,'action':'skill','source':'holy0','ability':'ability/ch9/coupled/duholy/Flame'}]
 with pytest.raises(ValueError):Compiler(providers=REG).compile(p)


def test_frozen_source_guard():assert guard()==START
