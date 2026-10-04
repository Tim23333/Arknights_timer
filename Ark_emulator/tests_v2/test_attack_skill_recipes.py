"""Physical damage/SP/control witnesses for source-backed synthetic recipes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ark_sim import Compiler,Engine
from ark_sim.domains.abilities import ActivationRejected
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_attack_skill_recipes import (build,ROOT,ANGEL_SKILL,ANGEL_NORMAL,ANGEL_BURST,CHEN_SKILL,CHEN_NORMAL)


@pytest.fixture(scope='module')
def packages():
    return {name:json.loads((ROOT/'packages/campaign'/f'skills.{name}.json').read_text(encoding='utf8'))
            for name in ('angel','chen')}


def run(package,ticks):
    sim=Engine.create(Compiler().compile(package),seed=71)
    sim.advance(ticks)
    return sim


def events(sim,kind,ability=None):
    return [e for e in sim.session.events if e['type']==kind and
            (ability is None or e['payload'].get('ability')==ability)]


@pytest.mark.parametrize('name',['angel','chen'])
def test_source_builder_and_actual_compiler_keep_partial_fixture_scope(packages,name):
    package=packages[name]
    assert build(name)==package
    assert package['status']=='partially_implemented'
    assert package['manifest']['metadata']['official_unit_config_imported'] is False
    assert package['manifest']['metadata']['client_validated'] is False
    assert package['entities'][0]['components']['attributes']['base']['atk']==100
    Compiler().compile(package)


def test_angel_auto_starts_after_ten_recovery_periods_with_synchronous_mode_switch(packages):
    sim=run(packages['angel'],299)
    assert sim.ctx.resources.current('actor','sp')==29
    assert not events(sim,'ability.started',ANGEL_SKILL)
    assert len(events(sim,'damage.accepted',ANGEL_NORMAL))==10
    assert sim.ctx.resources.current('target','hp')==99100
    sim.advance(1)
    assert [e['time'] for e in events(sim,'ability.started',ANGEL_SKILL)]==[299]
    assert sim.ctx.resources.current('actor','sp')==0
    assert sim.ctx.resources.current('actor','mode')==1
    assert sim.ctx.attributes.value('actor','attack_interval')==pytest.approx(0.89)
    assert sim.ctx.attributes.value('actor','attack_times')==5
    sim.advance(1)
    assert [e['time'] for e in events(sim,'ability.started',ANGEL_BURST)]==[300]
    assert not [e for e in events(sim,'ability.started',ANGEL_NORMAL) if e['time']>=299]


def test_angel_full_sp_player_force_is_rejected_without_mutation_and_auto_system_still_starts(packages):
    data=deepcopy(packages['angel'])
    data['entities'][0]['components']['resources']['sp']['initial']=30
    sim=Engine.create(Compiler().compile(data),seed=71)
    before=sim.snapshot()
    with pytest.raises(ActivationRejected,match='[Aa]utomatic'):
        sim.ctx.abilities.start('actor',ANGEL_SKILL,automatic=False)
    assert first_difference(before,sim.snapshot()) is None
    assert sim.ctx.resources.current('actor','sp')==30
    assert sim.ctx.resources.current('actor','mode')==0
    sim.submit({'action':'activate_ability','source':'actor','ability':ANGEL_SKILL})
    sim.advance(1)
    assert events(sim,'command.rejected')
    assert len(events(sim,'ability.started',ANGEL_SKILL))==1
    assert sim.ctx.resources.current('actor','sp')==0
    assert sim.ctx.resources.current('actor','mode')==1
    costs=[e for e in events(sim,'resource.changed',ANGEL_SKILL)
           if e['payload'].get('reason')=='ability_cost' and e['payload'].get('resource')=='sp']
    assert len(costs)==1 and costs[0]['payload']['delta']==-30


def test_angel_five_physical_projectiles_and_one_attack_event(packages):
    sim=run(packages['angel'],310)
    assert sim.ctx.resources.current('target','hp')==99100  # Launch309, arrival310 not executed yet.
    sim.advance(9)
    damage=events(sim,'damage.accepted',ANGEL_BURST)
    assert [e['time'] for e in damage]==[310,312,314,316,318]
    assert [e['payload']['amount'] for e in damage]==pytest.approx([100]*5)  # 100*1.1 - DEF10.
    assert sim.ctx.resources.current('target','hp')==98600
    assert len(events(sim,'attack.accepted',ANGEL_BURST))==1
    launches=events(sim,'projectile.launched',ANGEL_BURST)
    assert [e['time'] for e in launches]==[309,311,313,315,317]
    assert all(e['payload']['flight_seconds']==pytest.approx(1/30) for e in launches)
    assert sim.ctx.resources.current('actor','sp')==0


def test_angel_dynamic_repeat_uses_modified_effective_attribute_not_fixed_five(packages):
    data=deepcopy(packages['angel'])
    data['buffs'].append({'id':'buff/synthetic_repeat_reduction','kind':'buff',
        'duration_seconds':15,'modifiers':[{'attribute':'attack_times','layer':'flat','value':-2}]})
    data['scenarioDraft']['dependencies']=['buff/synthetic_repeat_reduction']
    sim=run(data,319)
    sim.ctx.buffs.apply('actor','actor','buff/synthetic_repeat_reduction')
    assert sim.ctx.attributes.value('actor','attack_times')==3
    sim.advance(36)
    starts=events(sim,'ability.started',ANGEL_BURST)
    assert [e['time'] for e in starts][:2]==[300,327]
    assert len([e for e in events(sim,'projectile.launched',ANGEL_BURST) if 327<=e['time']<354])==3


def test_angel_skill_expiry_restores_normal_mode_and_sp_recovery(packages):
    sim=run(packages['angel'],749)
    assert sim.ctx.resources.current('actor','mode')==1
    assert sim.ctx.resources.current('actor','sp')==0
    sim.advance(1)
    assert sim.ctx.resources.current('actor','mode')==0
    assert sim.ctx.attributes.value('actor','attack_interval')==1
    assert sim.ctx.attributes.value('actor','attack_times')==1
    sim.advance(31)
    assert sim.ctx.resources.current('actor','sp')==1
    resumed=[e for e in events(sim,'damage.accepted',ANGEL_NORMAL) if e['time']>=749]
    assert resumed and all(e['payload']['amount']==90 for e in resumed)


def test_angel_automatic_mode_can_start_without_targets_but_does_not_fake_hits(packages):
    data=deepcopy(packages['angel'])
    data['scenarioDraft']['initialEntities']=data['scenarioDraft']['initialEntities'][:1]
    sim=run(data,301)
    assert len(events(sim,'ability.started',ANGEL_SKILL))==1
    assert sim.ctx.resources.current('actor','sp')==0
    assert sim.ctx.resources.current('actor','mode')==1
    assert not events(sim,'damage.accepted') and not events(sim,'attack.accepted')


def test_angel_each_shot_can_reselect_when_previous_target_dies(packages):
    data=deepcopy(packages['angel'])
    data['entities'][0]['components']['resources']['sp']['initial']=30
    data['entities'][1]['components']['resources']['hp']['initial']=150
    data['scenarioDraft']['initialEntities'].append({'definition':data['entities'][1]['id'],
        'instanceAlias':'second','position':{'row':1,'col':2},
        'components':{'resources':{'hp':{'initial':100000}}}})
    sim=run(data,20)
    assert sim.ctx.alive('target') is False
    damage=events(sim,'damage.accepted',ANGEL_BURST)
    assert len(damage)==5
    assert [e['payload']['target'] for e in damage][2:]==[sim.session.world.resolve('second')]*3
    assert len(events(sim,'attack.accepted',ANGEL_BURST))==1


def test_chen_normal_double_hits_charge_once_and_next_attack_replaces_both(packages):
    sim=run(packages['chen'],180)
    normal=events(sim,'damage.accepted',CHEN_NORMAL)
    assert [e['time'] for e in normal]==[13,30,58,75,103,120,148,165]
    assert [e['payload']['amount'] for e in normal]==[90]*8
    assert [e['time'] for e in events(sim,'attack.accepted',CHEN_NORMAL)]==[13,58,103,148]
    assert sim.ctx.resources.current('actor','sp')==4
    assert not events(sim,'ability.started',CHEN_SKILL)
    sim.advance(1)
    assert [e['time'] for e in events(sim,'ability.started',CHEN_SKILL)]==[180]
    assert sim.ctx.resources.current('actor','sp')==0
    assert not [e for e in events(sim,'ability.started',CHEN_NORMAL) if e['time']==180]
    sim.advance(16)
    skill=events(sim,'damage.accepted',CHEN_SKILL)
    assert [e['time'] for e in skill]==[196]
    assert skill[0]['payload']['amount']==310  # 100*3.2 - DEF10, physical.
    assert sim.ctx.resources.current('target','hp')==98970
    assert sim.ctx.resources.current('actor','sp')==0  # Native allow-SP-while-affecting=false.
    sim.advance(60)
    assert any(e['time']==238 for e in events(sim,'damage.accepted',CHEN_NORMAL))
    assert sim.ctx.resources.current('actor','sp')==1


def test_chen_auto_replacement_cannot_be_forced_by_player_command(packages):
    sim=Engine.create(Compiler().compile(packages['chen']))
    sim.submit({'action':'activate_ability','source':'actor','ability':CHEN_SKILL})
    sim.advance(1)
    assert events(sim,'command.rejected')
    assert not events(sim,'ability.started',CHEN_SKILL)
    assert sim.ctx.resources.current('actor','sp')==0


def test_chen_stun_stops_movement_attack_and_abilities_then_restores_at_half_open_expiry(packages):
    data=deepcopy(packages['chen'])
    enemy=data['entities'][1]
    enemy['components']['attributes']['base']['move_speed']=0.02
    enemy['components']['abilities']=['ability/synthetic_enemy_attack']
    data['abilities'].append({'id':'ability/synthetic_enemy_attack','kind':'ability',
        'activation':{'mode':'automatic_attack'},'selector':'selector/synthetic_player',
        'timeline':[{'at_seconds':0.4,'effect':{'op':'damage','damage_type':'physical'}}]})
    data['selectors'].append({'id':'selector/synthetic_player','kind':'selector','region':{'type':'all'},
                            'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
    data['scenarioDraft']['initialEntities'][1]['route']={'motionMode':'WALK','endPosition':{'row':2,'col':4}}
    sim=run(data,197)
    assert sim.ctx.buffs.controls('target')=={'move':False,'attack':False,'abilities':False,'block':False}
    point=sim.ctx.get('target',('spatial','position'))
    sim.advance(44)
    assert sim.ctx.get('target',('spatial','position'))==point
    assert not [e for e in events(sim,'ability.started','ability/synthetic_enemy_attack') if 197<=e['time']<241]
    assert sim.ctx.buffs.controls('target')=={'move':True,'attack':True,'abilities':True,'block':True}
    sim.advance(1)
    assert sim.ctx.get('target',('spatial','position'))['col']>point['col']
    assert any(e['time']==241 for e in events(sim,'ability.started','ability/synthetic_enemy_attack'))


def test_chen_no_target_keeps_full_sp_and_does_not_cast_or_pay(packages):
    data=deepcopy(packages['chen'])
    data['entities'][0]['components']['resources']['sp']['initial']=4
    data['scenarioDraft']['initialEntities']=data['scenarioDraft']['initialEntities'][:1]
    sim=run(data,60)
    assert sim.ctx.resources.current('actor','sp')==4
    assert not events(sim,'ability.started',CHEN_SKILL)
    assert not events(sim,'damage.accepted')


def test_chen_stun_interrupts_existing_enemy_windup_before_its_hit(packages):
    data=deepcopy(packages['chen'])
    data['entities'][0]['components']['resources']['sp']['initial']=4
    data['entities'][1]['components']['abilities']=['ability/synthetic_windup']
    data['abilities'].append({'id':'ability/synthetic_windup','kind':'ability',
        'activation':{'mode':'manual'},'selector':'selector/synthetic_player',
        'timeline':[{'at_seconds':1,'effect':{'op':'damage','damage_type':'physical'}}]})
    data['selectors'].append({'id':'selector/synthetic_player','kind':'selector','region':{'type':'all'},
                            'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
    sim=Engine.create(Compiler().compile(data))
    sim.submit({'action':'activate_ability','source':'target','ability':'ability/synthetic_windup'})
    sim.advance(17)  # S1 hits16 and cancels the already-started t30 attack.
    interrupted=events(sim,'ability.interrupted','ability/synthetic_windup')
    assert len(interrupted)==1 and interrupted[0]['time']==16
    sim.advance(44)
    assert not events(sim,'damage.accepted','ability/synthetic_windup')
    assert sim.ctx.resources.current('actor','hp')==10000


def test_chen_lethal_hit_settles_real_death_without_applying_stun_to_corpse(packages):
    data=deepcopy(packages['chen'])
    data['entities'][0]['components']['resources']['sp']['initial']=4
    data['entities'][1]['components']['resources']['hp']['initial']=300
    sim=run(data,17)
    assert sim.ctx.alive('target') is False
    assert sim.ctx.state()['kills']==1
    assert sim.ctx.resources.current('actor','sp')==0
    assert len(events(sim,'damage.accepted',CHEN_SKILL))==1
    assert not events(sim,'buff.applied')


def test_angel_mode_cleanup_requires_correct_source_and_target(packages):
    sim=run(packages['angel'],301)
    actor=sim.session.world.resolve('actor');target=sim.session.world.resolve('target')
    sim.ctx.emit('buff.removed',{'source':target,'target':actor,'buff':'buff/campaign_angel_overload'})
    sim.advance(1)
    assert sim.ctx.resources.current('actor','mode')==1
    sim.ctx.buffs.remove('actor','buff/campaign_angel_overload')
    sim.advance(1)
    assert sim.ctx.resources.current('actor','mode')==0
    assert sim.ctx.attributes.value('actor','attack_times')==1


def test_other_selected_skills_are_not_silently_substituted():
    with pytest.raises(ValueError,match='Unsupported attack recipe'):
        build('kalts')


@pytest.mark.parametrize('name,tick,end',[('angel',350,790),('chen',190,280)])
def test_attack_mode_checkpoint_and_input_replay_are_exact(packages,name,tick,end):
    program=Compiler().compile(packages[name])
    sim=Engine.create(program,seed=71)
    sim.advance(tick)
    checkpoint=sim.checkpoint()
    sim.advance(end-tick)
    expected=sim.snapshot()
    resumed=Engine.restore(program,checkpoint)
    resumed.advance(end-tick)
    assert first_difference(expected,resumed.snapshot()) is None
    assert first_difference(expected,replay(program,sim.export_replay()).snapshot()) is None
