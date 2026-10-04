"""Additional real source boundaries; modules and previous goldens remain frozen."""
from copy import deepcopy
from tools.chapter08_special.test_author_v3 import package,make,ability,fixed_damage,packets
import pytest
def test_empace_ASPD2_scales_native_windup_busy_and_main_clock():
 p=package('empace',True);b='buff/test/c8/speed2';p['buffs'].append({'id':b,'kind':'buff','modifiers':[{'attribute':'attack_speed_ratio','layer':'direct_ratio','value':1}]});p['entities'][0]['components']['buffs']['initial'].append(b);s=make(p);s.session.advance(80)
 assert [(e['time'],e['payload']['amount']) for e in packets(s,'near')]==[(8,800),(76,800)]
 assert [e['time'] for e in s.session.events if e['type']=='ability.finished' and e['payload']['source']==s.session.world.resolve('enemy')]==[23]
def test_empace_true_public_deploy_withdraw_releases_block_and_no_ghost_pending_hit():
 p=package('empace',True);unit=p['entities'][1]['id'];p['scenarioDraft']['initialEntities']=[e for e in p['scenarioDraft']['initialEntities'] if e['instanceAlias']!='near'];p['scenarioDraft']['roster']=[unit];s=make(p)
 s.submit({'action':'deploy','entity':unit,'row':2,'col':2,'alias':'near'},at=0);s.submit({'action':'withdraw','source':'near'},at=5);s.session.advance(50)
 assert not packets(s,'near') and not s.ctx.alive('near') and s.ctx.get('enemy',('runtime','blocked_by')) is None
 assert [e['type'] for e in s.session.events if e['type'].startswith('command.')]==['command.accepted','command.accepted']
 assert s.ctx.resources.current('system/battle','dp')==19
def test_empace_public_lethal_damage_single_death_and_no_postdeath_attack():
 p=package('empace',True);d=fixed_damage(p,12000);s=make(p);s.submit({'action':'skill','source':'near','ability':d},at=5);s.session.advance(160)
 assert s.ctx.resources.current('enemy','hp')==0 and not s.ctx.alive('enemy') and not packets(s,'near')
 assert len([e for e in s.session.events if e['type']=='entity.died' and e['payload']['target']==s.session.world.resolve('enemy')])==1
def test_empace_actual_flight_target_retire_cannot_damage_others():
 p=package('empace');a=ability(p,'retire_target',{'op':'retire','target':'source','parameters':{'reason':'controlled_target_retire'}});s=make(p);s.submit({'action':'skill','source':'near','ability':a},at=32);s.session.advance(40)
 assert not s.ctx.alive('near') and not packets(s)
@pytest.mark.parametrize('name,end',[('emppnt',230),('empace',180)])
def test_original_route_leak_and_exact_source_life_cost_without_targets(name,end):
 p=package(name);p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];p['scenarioDraft']['resources']['life']={'initial':3,'capacity':3};s=make(p);s.session.advance(end)
 assert not s.ctx.alive('enemy') and s.ctx.resources.current('system/battle','life')==2
 assert len([e for e in s.session.events if e['type']=='entity.leaked'])==1 and not packets(s)
def test_emppnt_target_camo_cannot_start_but_area_camo_is_source_ignored():
 p=package('emppnt');p['scenarioDraft']['initialEntities']=[e for e in p['scenarioDraft']['initialEntities'] if e['instanceAlias'] in ('enemy','camo')];s=make(p);s.session.advance(30)
 assert not [e for e in s.session.events if e['type']=='projectile.launched']
