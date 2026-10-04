"""Independent counterexamples for M5. No client/formal approval is implied."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from ark_sim import Compiler, Engine
from ark_sim.rules.expressions import evaluate_expression
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene
from tools.build_campaign_squad import build as squad

ROOT = Path(__file__).resolve().parents[1]


def make(data):
    return Engine.create(Compiler().compile(data), seed=502)


def events(sim, kind):
    return [e for e in sim.session.events if e['type'] == kind]


def token_model():
    data = scene()
    data['scenarioDraft']['resources'] = {'dp': {'initial': 10, 'capacity': 99}}
    data['entities'].append({'id':'unit/child', 'kind':'entity', 'tags':['token'],
        'components':{'attributes':{'base':{'atk':1}}, 'spatial':{}, 'abilities':['ability/child']}})
    data['abilities'].append({'id':'ability/child','kind':'ability', 'activation':{'mode':'manual'},
        'timeline':[{'at':0,'effect':{'op':'emit','event':'review.child_attack'}}]})
    data['abilities'][0] = {'id':'ability/probe','kind':'ability','activation':{'mode':'manual',
        'costs':[{'owner':'battle','resource':'dp','amount':5}],
        'on_start':[{'op':'spawn','definition':'unit/child','owner':'source','lifetime_seconds':.1,
            'parameters':{'max_owned':1,'on_owner_retire':'remove'}}]},'timeline':[]}
    return data


def children(sim):
    return [e for e in sim.session.world.entities() if e['definition_id']=='unit/child']


def test_alias_owner_retire_and_child_alias_canonicalization():
    sim=make(token_model())
    sim.ctx.abilities.start('source','ability/probe')
    child=children(sim)[0]['id']
    assert sim.ctx.get(child,('ownership','owner')) == sim.session.world.resolve('source')
    sim.ctx.lifecycle.retire('source','withdrawn')
    assert not sim.ctx.alive(child)
    assert sim.ctx.get(child,('runtime','state')) == 'owner_retired'


def test_owned_capacity_failure_rolls_back_battle_payment_and_all_public_state():
    sim=make(token_model()); sim.ctx.abilities.start('source','ability/probe'); sim.advance(1)
    before=deepcopy(sim.snapshot()); log=deepcopy(sim.session.events)
    with pytest.raises(ValueError,match='capacity'):
        sim.ctx.abilities.start('source','ability/probe')
    assert sim.snapshot()==before and sim.session.events==log
    assert sim.ctx.resources.current('system/battle','dp')==5


def test_lifetime_half_open_rejects_command_at_exact_expiry_before_effectphase():
    sim=make(token_model()); sim.ctx.abilities.start('source','ability/probe')
    child=children(sim)[0]['id']
    sim.submit({'action':'skill','source':child,'ability':'ability/child'},at=3)
    sim.advance(4)
    assert not events(sim,'review.child_attack')
    assert not sim.ctx.alive(child)
    assert events(sim,'command.rejected')


def test_zero_lifetime_child_never_survives_to_first_command_tick():
    data=token_model();data['abilities'][0]['activation']['on_start'][0]['lifetime_seconds']=0
    sim=make(data);sim.ctx.abilities.start('source','ability/probe')
    child=children(sim)[0]['id'];sim.submit({'action':'skill','source':child,'ability':'ability/child'},at=0)
    sim.advance(1)
    assert not events(sim,'review.child_attack')


def projectile_model(area=False):
    data=scene();data['selectors'][0]['limit']=1 if area else 2
    a=data['abilities'][0];a['parameters']={'projectile_speed':2,'wait_for_projectiles':True}
    hit={'op':'damage','damage_type':'true','on_success':[{'op':'schedule','delay_seconds':.2,
        'effect':{'op':'emit','event':'review.delayed'}}]}
    if area:hit={'op':'area','center':'target','radius':.3,'filters':[{'tag':'enemy'}],'effects':[hit]}
    a['timeline']=[{'at':0,'effect':hit}]
    return data


def test_multiple_packets_wait_for_slowest_and_nested_schedule_is_not_completion():
    sim=make(projectile_model());sim.ctx.abilities.start('source','ability/probe');sim.advance(1)
    cast=next(iter(sim.ctx.get('source',('runtime','casts')).values()))
    assert cast['pending_projectiles']==2
    sim.advance(30)
    cast=next(iter(sim.ctx.get('source',('runtime','casts')).values()))
    assert cast['pending_projectiles']==1 and not events(sim,'ability.finished')
    sim.advance(15)
    assert len(events(sim,'ability.finished'))==1
    sim.advance(8)
    assert len(events(sim,'review.delayed'))==2
    assert len(events(sim,'ability.finished'))==1


def test_one_area_packet_reselects_live_impact_members_after_launch():
    sim=make(projectile_model(area=True));sim.ctx.abilities.start('source','ability/probe');sim.advance(1)
    sim.ctx.movement.displace('source','target2',{'position':{'row':0,'col':2.1}},None)
    sim.advance(30)
    assert len(events(sim,'projectile.launched'))==1
    assert len(events(sim,'area.resolved'))==1
    assert sim.ctx.resources.current('target1','hp')==90
    assert sim.ctx.resources.current('target2','hp')==90


def motion_model(mode='extend'):
    data=scene();data['entities'][1]['components']['attributes']['base']['mass_level']=0
    data['entities'][1]['components']['lifecycle']={'policy':'policy/ark_lifecycle'}
    data['rules']=[{'id':'rule/reviewpush','kind':'calculation_rule','contract':'movement.displacement',
        'implementation':{'type':'expression','expression':"{'distance':inputs.distance if inputs.force > inputs.mass else 0,'duration':0.2 if inputs.force > inputs.mass else 0}"}},
        {'id':'rule/reviewdistance','kind':'calculation_rule','contract':'damage.pipeline',
        'implementation':{'type':'graph','nodes':[{'id':'settle','expression':"{'accepted':True,'amount':inputs.effect.distance*100,'allocations':[],'events':[]}"}], 'output':'nodes.settle'}}]
    data['buffs']=[{'id':'buff/reviewdistance','kind':'buff','duration_seconds':1,'interval_seconds':.8,
        'stacking':{'mode':mode,'identity':['definition','target'],'max_stacks':1},
        'movement_damage':{'effect':{'op':'damage','damage_type':'true','rules':{'damage.pipeline':'rule/reviewdistance'}}}}]
    data['scenarioDraft']['dependencies']=['buff/reviewdistance','rule/reviewpush']
    return data


def push(sim,distance=1,**parameters):
    sim.ctx.movement.push('source','target1',{'force':3,'distance':distance,'direction':'source_facing',
        'parameters':parameters,'rules':{'movement.displacement':'rule/reviewpush'}},None)


def test_repush_cancels_old_generation_and_boundary_clips_actual_ledger():
    sim=make(motion_model());push(sim,2);sim.advance(2)
    push(sim,.2);sim.advance(10)
    assert sim.ctx.get('target1',('spatial','distance_travelled'))==pytest.approx(2/6+.2)
    assert not sim.ctx.get('target1',('spatial','forced_motion'))
    push(sim,100);sim.advance(10)
    assert sim.ctx.get('target1',('spatial','position'))['col'] < 4.5
    assert sim.ctx.get('target1',('spatial','distance_travelled'))==pytest.approx(2.5)


def test_effect_mass_attribute_reads_live_buff_layer_instead_of_default_mass():
    data=motion_model();data['entities'][1]['components']['attributes']['base']['review_mass']=2
    data['buffs'].append({'id':'buff/heavy','kind':'buff','duration_seconds':1,
        'modifiers':[{'attribute':'review_mass','layer':'flat','value':2}]})
    data['scenarioDraft']['dependencies'].append('buff/heavy')
    sim=make(data);sim.ctx.buffs.apply('source','target1','buff/heavy');push(sim,mass_attribute='review_mass')
    sim.advance(10)
    assert sim.ctx.get('target1',('spatial','position'))['col']==2
    assert not events(sim,'movement.traveled')


@pytest.mark.parametrize('mode',['refresh','extend'])
def test_merge_flushes_tail_then_new_cursor_and_lethal_remove_never_double_counts(mode):
    sim=make(motion_model(mode));uid=sim.ctx.buffs.apply('source','target1','buff/reviewdistance')
    sim.ctx.movement.displace('source','target1',{'offset':{'row':0,'col':.2}},None)
    sim.ctx.buffs.apply('source','target1','buff/reviewdistance')
    assert sim.ctx.resources.current('target1','hp')==pytest.approx(80)
    sim.ctx.movement.displace('source','target1',{'offset':{'row':0,'col':.9}},None)
    sim.ctx.buffs.remove('target1',uid)
    assert len(events(sim,'buff.movement_sample'))==2
    assert len(events(sim,'damage.accepted'))==2
    assert sim.ctx.resources.current('target1','hp')==pytest.approx(0)
    assert not sim.ctx.alive('target1')
    assert len(events(sim,'entity.died'))==1
    sim.advance(40)
    assert len(events(sim,'damage.accepted'))==2


def test_all_twelve_integrated_stats_sourcehashes_and_selected_skill_ownership():
    data=squad();norm=json.loads((ROOT/'packages/campaign/operators.normalized.json').read_text(encoding='utf8'))
    actors={e['metadata']['native_id']:e for e in data['entities'] if 'campaign_roster' in e.get('tags',[])}
    mapping={'max_hp':'maxHp','atk':'atk','def':'def','mres':'magicResistance','attack_interval':'baseAttackTime',
        'block_count':'blockCnt','deploy_cost':'cost','mass_level':'massLevel'}
    assert len(actors)==12
    for record in norm['operators']:
        e=actors[record['character_id']];attrs=e['components']['attributes']['base']
        for model,native in mapping.items():assert attrs[model]==record['stats']['model_stats'][native]
        assert e['metadata']['selected_skill_native_id']==record['selected_skill']['skill_id']
        assert e['metadata']['selected_skill_ability'] in e['components']['abilities']
        assert len(e['components']['abilities'])==len(set(e['components']['abilities']))
    for name,digest in data['manifest']['metadata']['source_packages'].items():
        assert hashlib.sha256((ROOT/f'packages/campaign/skills.{name}.json').read_bytes()).hexdigest()==digest
    assert data['manifest']['metadata']['formal_mainline_approved'] is False


def test_integrated_owned_spawn_contains_no_probe_position_or_facing():
    data=squad()
    for ability in data['abilities']:
        for effect in ability.get('activation',{}).get('on_start',[]):
            if effect['op']=='spawn' and effect.get('owner')=='source':
                assert 'position' not in effect, (ability['id'],effect)
                assert 'facing' not in effect, (ability['id'],effect)


def squad_scene():
    data=squad();data['scenarioDraft']={'id':'scenario/review_squad','ruleset':'ruleset/ark_standard',
        'map':{'rows':9,'cols':14},'resources':{'dp':{'initial':50,'capacity':99}},
        'initialEntities':[{'definition':'unit/char_400_weedy','instanceAlias':'host',
            'position':{'row':7,'col':10},'facing':'up'}]}
    return data


def test_real_squad_deployment_uses_explicit_far_from_probe_position_and_facing():
    sim=make(squad_scene())
    sim.submit({'action':'skill','source':'host','ability':'ability/campaign_weedy_deploy_cannon',
        'payload':{'position':{'row':7,'col':11},'facing':'left'}})
    sim.advance(1)
    owned=[e for e in sim.session.world.entities() if e['components'].get('ownership',{}).get('owner')==sim.session.world.resolve('host')]
    assert len(owned)==1
    assert owned[0]['components']['spatial']['position']=={'row':7,'col':11}
    assert owned[0]['components']['spatial']['facing']=='left'
    assert sim.ctx.resources.current('system/battle','dp')==45


@pytest.mark.parametrize('payload',[None,{'position':{'row':9,'col':11}},
    {'position':{'row':7.1,'col':11}}, {'position':{'row':True,'col':11}},
    {'position':{'row':7,'col':11},'facing':'diagonal'}])
def test_real_squad_invalid_deployment_payload_preserves_payment_and_entities(payload):
    sim=make(squad_scene());before=deepcopy(sim.snapshot());log=deepcopy(sim.session.events)
    with pytest.raises(ValueError):
        sim.ctx.abilities.start('host','ability/campaign_weedy_deploy_cannon',event_payload=payload)
    assert sim.snapshot()==before and sim.session.events==log


def test_on_remove_mode_cleanup_precedes_exact_endtick_autoattack_sampling():
    data=scene(mode='automatic_attack');data['entities'][0]['components']['resources']['mode']={'initial':1,'capacity':1}
    data['entities'][0]['components']['attributes']['base']['attack_interval']=.1
    data['abilities'][0]['activation']['condition']='inputs.resources.mode.current == 0'
    data['abilities'][0]['selector']='selector/probe';data['selectors'][0]['limit']=1
    data['buffs']=[{'id':'buff/mode','kind':'buff','duration_seconds':.1,
        'on_remove':[{'op':'modify_resource','target':'source','resource':'mode','value':0}],
        'modifiers':[{'attribute':'atk','layer':'flat','value':20}]}]
    data['scenarioDraft']['dependencies']=['buff/mode']
    sim=make(data);sim.ctx.buffs.apply('source','source','buff/mode');sim.advance(4)
    assert [(e['time'],e['payload']['amount']) for e in events(sim,'damage.accepted')]==[(3,10)]
    assert sim.ctx.resources.current('source','mode')==0


def test_owned_recovery_gate_excludes_foreign_and_clears_on_exact_child_expiry():
    data=token_model();data['entities'][0]['components']['resources']['sp']={
        'initial':8,'capacity':20,'recovery_rate':1,'recovery':{'mode':'continuous',
            'selector':'selector/reviewowned','selector_interval_seconds':1/30,'empty_value':0,'interrupt_when_empty':True}}
    data['selectors'].append({'id':'selector/reviewowned','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'token'},{'owner':'source'},{'state':'alive'}],'limit':1})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/source','instanceAlias':'foreign',
        'position':{'row':0,'col':1}})
    sim=make(data);sim.ctx.abilities.start('foreign','ability/probe');sim.advance(2)
    assert sim.ctx.resources.current('source','sp')==0
    assert sim.ctx.resources.current('foreign','sp')>8
    sim.advance(2)
    assert sim.ctx.resources.current('foreign','sp')==0


def test_time_curve_at_cast_keeps_capture_clock_but_endtick_new_cast_has_no_buff():
    data=scene();data['rules']=[{'id':'rule/reviewclock','kind':'calculation_rule','extends':'rule/ark_attribute_layers',
        'implementation':{'type':'provider','provider':'ark.attributes.time_layers'}}]
    data['entities'][0]['rules']={'attributes.effective':'rule/reviewclock'}
    data['buffs']=[{'id':'buff/clock','kind':'buff','duration_seconds':.2,
        'modifiers':[{'attribute':'atk','layer':'direct_ratio','value':2,
            'parameters':{'time_curve':{'type':'linear_remaining'}}}]}]
    data['scenarioDraft']['dependencies']=['buff/clock']
    data['selectors'][0]['limit']=1
    data['abilities'][0]['timeline']=[{'at':8,'effect':{'op':'damage','damage_type':'true',
        'read_mode':{'source_attributes':'at_cast'}}}]
    sim=make(data);sim.ctx.buffs.apply('source','source','buff/clock')
    sim.advance(3);sim.ctx.abilities.start('source','ability/probe')
    sim.advance(9)
    assert sim.ctx.resources.current('target1','hp')==80
    assert sim.ctx.attributes.value('source','atk')==10


def test_independent_wall_collision_and_checkpoint_replay_keep_actual_ledger():
    data=motion_model();data['scenarioDraft']['map']['tiles']=[
        {'tileKey':'tile_floor','passableMask':1} if col!=3 else {'tileKey':'tile_wall','passableMask':0}
        for col in range(5)]
    data['abilities'][0]['timeline']=[{'at':0,'effects':[
        {'op':'apply_buff','buff':'buff/reviewdistance'},
        {'op':'push','force':3,'distance':4,'direction':'source_facing',
            'rules':{'movement.displacement':'rule/reviewpush'}}]}]
    data['selectors'][0]['limit']=1
    program=Compiler().compile(data);sim=Engine.create(program,seed=502)
    sim.submit({'action':'skill','source':'source','ability':'ability/probe'})
    sim.advance(2);restored=Engine.restore(program,sim.checkpoint())
    sim.advance(32);restored.advance(32)
    assert first_difference(sim.snapshot(),restored.snapshot()) is None
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None
    assert sim.ctx.get('target1',('spatial','distance_travelled'))==pytest.approx(.5)
    assert sim.ctx.resources.current('target1','hp')==pytest.approx(50)


def test_squad_ordinary_attack_modes_do_not_own_duplicate_eligible_clocks():
    data=squad();abilities={a['id']:a for a in data['abilities']}
    for actor in data['entities']:
        if 'campaign_roster' not in actor.get('tags',[]):continue
        resources={name:{'current':spec.get('initial',0)} for name,spec in actor['components']['resources'].items()}
        for mode in (0,1):
            if 'mode' in resources:resources['mode']['current']=mode
            eligible=[]
            for key in actor['components']['abilities']:
                a=abilities[key];activation=a.get('activation',{})
                if activation.get('mode')!='automatic_attack':continue
                if activation.get('parameters',{}).get('replace_attack'):continue
                condition=activation.get('condition')
                if not condition or evaluate_expression(condition,{'resources':resources},{}):eligible.append(key)
            assert len(eligible)<=1,(actor['id'],mode,eligible)
