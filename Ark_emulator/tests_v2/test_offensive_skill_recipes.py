"""Offensive scope: real stats/packets; unproven random FSM is never certified."""
from copy import deepcopy

import pytest

from ark_sim import Compiler,Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_offensive_skill_recipes import (ROOT,read,build,BPIPE_SKILL,BPIPE_NORMAL,BPIPE_BURST,
                                                AMGOAT_SKILL,AMGOAT_NORMAL,AMGOAT_PACKET)


@pytest.fixture(scope='module')
def packages():
    return {name:read(ROOT/'packages/campaign'/f'skills.{name}.json') for name in ('bpipe','amgoat')}


def events(sim,kind,ability=None):
    return [e for e in sim.session.events if e['type']==kind and (ability is None or e['payload'].get('ability')==ability)]


def initialized(data):
    return Engine.create(Compiler().compile(data),seed=13)


def start_skill(data,name):
    data=deepcopy(data)
    data['entities'][0]['components']['resources']['sp']['initial']=40 if name=='bpipe' else 80
    sim=initialized(data)
    sim.submit({'action':'activate_ability','source':'actor','ability':BPIPE_SKILL if name=='bpipe' else AMGOAT_SKILL})
    sim.advance(1)
    return sim


@pytest.mark.parametrize('name',['bpipe','amgoat'])
def test_build_source_and_partial_complete_rejection(packages,name):
    assert build(name)==packages[name]
    assert packages[name]['status']=='partially_implemented'
    assert packages[name]['manifest']['metadata']['official_unit_complete'] is False
    assert packages[name]['manifest']['metadata']['client_validated'] is False
    with pytest.raises(ValueError,match='complete.*unsupported'):
        build(name,require_complete=True)
    Compiler().compile(packages[name])


def test_bpipe_requires_actual_fifteen_time_sp_periods_not_damage_hits(packages):
    sim=initialized(packages['bpipe'])
    sim.submit({'action':'activate_ability','source':'actor','ability':BPIPE_SKILL})
    sim.advance(1)
    assert events(sim,'command.rejected')
    assert sim.ctx.resources.current('actor','sp')==25
    sim.advance(448)
    assert sim.ctx.resources.current('actor','sp')==39
    assert len(events(sim,'attack.accepted',BPIPE_NORMAL))==15
    sim.advance(1)
    assert sim.ctx.resources.current('actor','sp')==40
    sim.submit({'action':'activate_ability','source':'actor','ability':BPIPE_SKILL})
    sim.advance(1)
    assert sim.ctx.resources.current('actor','sp')==0
    assert sim.ctx.resources.current('actor','mode')==1


def test_bpipe_source_scalers_and_three_distinct_spine_events(packages):
    sim=start_skill(packages['bpipe'],'bpipe')
    assert sim.ctx.attributes.value('actor','atk')==pytest.approx(220)
    assert sim.ctx.attributes.value('actor','def')==pytest.approx(220)
    assert sim.ctx.attributes.value('actor','block_count')==2
    assert sim.ctx.attributes.value('actor','attack_interval')==pytest.approx(1.7)
    sim.advance(13)
    assert not events(sim,'damage.accepted',BPIPE_BURST)
    sim.advance(7)
    damage=events(sim,'damage.accepted',BPIPE_BURST)
    assert [e['time'] for e in damage]==[14,17,20]
    assert [e['payload']['amount'] for e in damage]==pytest.approx([210]*3)
    assert len(events(sim,'attack.accepted',BPIPE_BURST))==1
    assert sim.ctx.resources.current('actor','sp')==0


def test_bpipe_interval_scaler_counterexample_is_not_add_point_seven(packages):
    data=deepcopy(packages['bpipe'])
    data['entities'][0]['components']['attributes']['base']['attack_interval']=2
    sim=start_skill(data,'bpipe')
    assert sim.ctx.attributes.value('actor','attack_interval')==pytest.approx(3.4)
    assert sim.ctx.attributes.value('actor','attack_interval')!=pytest.approx(2.7)


def test_bpipe_ground_filter_does_not_hit_flying_target(packages):
    data=deepcopy(packages['bpipe']);data['entities'][1]['tags']=['enemy','flying']
    sim=start_skill(data,'bpipe');sim.advance(60)
    assert not events(sim,'damage.accepted')
    assert sim.ctx.resources.current('target','hp')==100000


def test_bpipe_skill_expiry_restores_stats_single_hit_and_time_sp(packages):
    sim=start_skill(packages['bpipe'],'bpipe')
    sim.advance(599)
    assert sim.ctx.resources.current('actor','mode')==1
    assert sim.ctx.resources.current('actor','sp')==0
    sim.advance(1)
    assert sim.ctx.resources.current('actor','mode')==0
    assert sim.ctx.attributes.value('actor','atk')==100
    assert sim.ctx.attributes.value('actor','def')==100
    assert sim.ctx.attributes.value('actor','block_count')==1
    assert sim.ctx.attributes.value('actor','attack_interval')==1
    sim.advance(50)
    assert sim.ctx.resources.current('actor','sp')>=1
    assert any(e['payload']['amount']==90 for e in events(sim,'damage.accepted',BPIPE_NORMAL) if e['time']>=600)


def eyja_many(data,count):
    copied=deepcopy(data)
    copied['scenarioDraft']['map']={'rows':9,'cols':9}
    copied['scenarioDraft']['initialEntities'][0]['position']={'row':4,'col':4}
    positions=[(4,5),(4,6),(5,4),(3,4),(4,3),(5,5),(3,5),(8,8)]
    enemy=copied['entities'][1];enemy['components']['attributes']['base']['mres']=20
    copied['scenarioDraft']['initialEntities']=copied['scenarioDraft']['initialEntities'][:1]+[
        {'definition':enemy['id'],'instanceAlias':f'target{i}','position':{'row':row,'col':col}}
        for i,(row,col) in enumerate(positions[:count])]
    return copied


def test_amgoat_twenty_five_sp_periods_and_no_invented_skill_packet_timer(packages):
    sim=initialized(packages['amgoat']);sim.advance(750)
    assert sim.ctx.resources.current('actor','sp')==80
    sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_SKILL})
    sim.advance(60)
    assert sim.ctx.resources.current('actor','sp')==0
    assert sim.ctx.attributes.value('actor','atk')==pytest.approx(230)
    assert sim.ctx.attributes.value('actor','attack_interval')==pytest.approx(0.5)
    assert sim.ctx.attributes.value('actor','max_targets')==6
    assert not events(sim,'damage.accepted',AMGOAT_PACKET)
    assert 'native_rng_fsm_unknown' in packages['amgoat']['manifest']['metadata']['pending_mechanics']


@pytest.mark.parametrize('count,expected',[(2,2),(4,4),(7,6)])
def test_amgoat_dynamic_live_candidates_use_real_maximum_not_fixed_six_hits(packages,count,expected):
    sim=start_skill(eyja_many(packages['amgoat'],count),'amgoat')
    rng_before=sim.session.random.snapshot()
    sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_PACKET})
    sim.advance(30)
    damage=events(sim,'damage.accepted',AMGOAT_PACKET)
    assert len(damage)==expected
    assert all(e['payload']['amount']==pytest.approx(184) for e in damage)  # 230*(1-.20), not physical220.
    assert len(events(sim,'attack.accepted',AMGOAT_PACKET))==1
    assert sim.ctx.resources.current('actor','sp')==0
    assert sim.session.random.snapshot()==rng_before  # This is a deterministic probe, not native random selection.


def test_amgoat_effective_limit_external_modifier_and_dead_outside_filter(packages):
    data=eyja_many(packages['amgoat'],8)
    data['buffs'].append({'id':'buff/synthetic_target_cap','kind':'buff','duration_seconds':15,
                          'modifiers':[{'attribute':'max_targets','layer':'flat','value':-3}]})
    data['scenarioDraft']['dependencies']=['buff/synthetic_target_cap']
    sim=start_skill(data,'amgoat')
    sim.ctx.lifecycle.retire('target0','dead')
    sim.ctx.buffs.apply('actor','actor','buff/synthetic_target_cap')
    assert sim.ctx.attributes.value('actor','max_targets')==3
    sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_PACKET});sim.advance(30)
    damaged={e['payload']['target'] for e in events(sim,'damage.accepted',AMGOAT_PACKET)}
    assert len(damaged)==3
    assert sim.session.world.resolve('target0') not in damaged
    assert sim.session.world.resolve('target7') not in damaged


def test_amgoat_probe_mode_gate_zero_target_rejection_and_skill_restore(packages):
    sim=initialized(packages['amgoat'])
    sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_PACKET});sim.advance(1)
    assert events(sim,'command.rejected') and not events(sim,'damage.accepted',AMGOAT_PACKET)
    sim=start_skill(packages['amgoat'],'amgoat')
    sim.advance(449)
    assert sim.ctx.resources.current('actor','mode')==1
    sim.advance(1)
    assert sim.ctx.resources.current('actor','mode')==0
    assert sim.ctx.attributes.value('actor','atk')==100
    assert sim.ctx.attributes.value('actor','max_targets')==1
    assert sim.ctx.attributes.value('actor','attack_interval')==pytest.approx(1.6)
    data=deepcopy(packages['amgoat']);data['scenarioDraft']['initialEntities']=data['scenarioDraft']['initialEntities'][:1]
    sim=start_skill(data,'amgoat');sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_PACKET});sim.advance(1)
    assert events(sim,'command.rejected')
    assert sim.ctx.resources.current('actor','sp')==0


def test_same_end_tick_mode_packet_is_rejected_after_synchronous_model_detach(packages):
    data=deepcopy(packages['amgoat']);data['entities'][1]['components']['attributes']['base']['mres']=20
    sim=start_skill(data,'amgoat')
    sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_PACKET},at=450)
    sim.advance(455)
    packets=events(sim,'damage.accepted',AMGOAT_PACKET)
    assert not packets
    assert events(sim,'command.rejected')
    assert sim.ctx.resources.current('actor','mode')==0
    # Native frame alignment remains separate from this corrected model ordering.
    with pytest.raises(ValueError,match='native_mode_detach_end_tick_client_alignment_pending'):
        build('amgoat',require_complete=True)


@pytest.mark.parametrize('name,end',[('bpipe',660),('amgoat',490)])
def test_offensive_checkpoint_and_replay_keep_identity_and_packet_events(packages,name,end):
    data=deepcopy(packages[name]);data['entities'][0]['components']['resources']['sp']['initial']=40 if name=='bpipe' else 80
    program=Compiler().compile(data);sim=Engine.create(program,seed=13)
    sim.submit({'action':'activate_ability','source':'actor','ability':BPIPE_SKILL if name=='bpipe' else AMGOAT_SKILL})
    if name=='amgoat':
        for tick in (1,35,80):sim.submit({'action':'activate_ability','source':'actor','ability':AMGOAT_PACKET},at=tick)
    sim.advance(25);checkpoint=sim.checkpoint();sim.advance(end-25);expected=sim.snapshot()
    restored=Engine.restore(program,checkpoint);restored.advance(end-25)
    assert first_difference(expected,restored.snapshot()) is None
    assert first_difference(expected,replay(program,sim.export_replay()).snapshot()) is None
