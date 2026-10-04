"""Original independent expectations, executed only against an explicit candidate."""
import os
from pathlib import Path
import pytest

if not os.environ.get('ARKSIM_M10_REVIEW_ROOT'):
    pytest.skip('M10 candidate review requires explicit isolated candidate runtime',allow_module_level=True)

from ark_sim import Compiler,Engine
from ark_sim.adapters import api
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools import canonical_summon_witness_support as h
from tools.witness_canonical_kalts import healing_fixture,base,summon,mon


def assert_candidate():
    expected=Path(os.environ['ARKSIM_M10_REVIEW_ROOT']).resolve()
    assert Path(api.__file__).resolve().is_relative_to(expected)


def test_chen_selected_cast_freezes_periodic_talent_without_freezing_normal_attack_sp():
    assert_candidate()
    from tools.witness_canonical_roster_trio import scene,actor,command,events,eq
    import tools.witness_canonical_roster_trio as trio
    trio.PACKAGE=Path(os.environ['CAMPAIGN_SUMMON_PACKAGE'])
    data=scene([actor('chen',sp=4)],enemy=None,target='chen')
    data['scenarioDraft']['waves']=[{'at':119,'definition':'unit/witness_enemy','position':{'row':4,'col':5},'instanceAlias':'enemy'}]
    sim=Engine.create(Compiler().compile(data),seed=11);sim.advance(122)
    eq(sim.ctx.resources.current('chen','sp'),0)
    starts=[e for e in events(sim,'ability.started') if e['payload']['ability']=='ability/campaign_chen_s1']
    assert len(starts)==1 and starts[0]['time']==119
    sim.advance(68)
    # S1 finishes135; normal starts158 and first frame13 hits171. Accepted
    # attack is emitted once at its first hit, not once per physical packet.
    normal=[e for e in events(sim,'attack.accepted') if e['payload']['ability']=='ability/campaign_chen_normal']
    assert len(normal)==1 and normal[0]['time']==171
    eq(sim.ctx.resources.current('chen','sp'),1)
    h.finish(sim)


def test_kalts_no_owned_token_still_heals_foreign_mon():
    assert_candidate()
    sim=healing_fixture(own=False);sim.advance(28)
    host=sim.session.world.resolve('host');target=mon(sim,'other')
    heals=[e for e in h.events(sim,'healing.accepted') if e['payload']['source']==host]
    assert len(heals)==1 and heals[0]['time']==27 and heals[0]['payload']['target']==target
    h.eq(sim.ctx.resources.current(target,'hp'),645)
    assert not [e for e in h.events(sim,'ability.interrupted') if e['payload']['source']==host]
    h.finish(sim)


def test_kalts_loss_clears_sp_interrupts_s3_and_preserves_inflight_ordinary_heal():
    assert_candidate()
    sim=h.make(base(sp=15,hp=1000));summon(sim)
    h.command(sim,'host','ability/kalts_host_s3',at=2)
    h.command(sim,'enemy','ability/kalts_witness_kill',at=3)
    sim.advance(15)
    host=sim.session.world.resolve('host')
    interrupted=[e for e in h.events(sim,'ability.interrupted') if e['payload']['source']==host]
    assert len(interrupted)==1 and interrupted[0]['payload']['ability']=='ability/kalts_host_s3'
    assert interrupted[0]['time']==6
    h.eq(sim.ctx.resources.current('host','sp'),0)
    heals=[e for e in h.events(sim,'healing.accepted') if e['payload']['source']==host]
    assert len(heals)==1 and heals[0]['time']==14 and heals[0]['payload']['amount']==468
    h.eq(sim.ctx.resources.current('host','hp'),1468)
    h.finish(sim)


def test_interrupt_late_pure_snapshot_rule_failure_rolls_back_tasks_world_events_rng():
    assert_candidate()
    data={'schemaVersion':2,'manifest':{'id':'package/m10_atomic_review','version':'1','requires':['preset/ark_standard']},
        'entities':[{'id':'unit/review_hold','kind':'entity','tags':['player'],'components':{
            'attributes':{'base':{'max_hp':1000,'atk':100,'def':0,'mres':0}},'spatial':{},
            'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'},
                'sp':{'initial':0,'capacity':10,'recovery_rate':1,'recovery_freeze_rule':'rule/review_snapshot_fail'}},
            'abilities':['ability/review_hold'],'buffs':{'initial':['buff/review_interrupt_sp']}}}],
        'abilities':[{'id':'ability/review_hold','kind':'ability','activation':{'mode':'manual'},'duration_seconds':20,'timeline':[]}],
        'buffs':[{'id':'buff/review_interrupt_sp','kind':'buff','events':[{'event':'ability.interrupted','effects':[
            {'op':'modify_resource','resource':'sp','delta':1,'parameters':{'respect_recovery_freeze':True}}]}]}],
        'rules':[{'id':'rule/review_snapshot_fail','kind':'calculation_rule','contract':'resource.recovery_freeze',
            'metadata':{'recovery_freeze_authority':'final_override'},
            'implementation':{'type':'expression','expression':'True if inputs.owner.components.runtime.casts != {} else 1 / 0'}}],
        'scenarioDraft':{'id':'scenario/review_hold','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':3},
            'initialEntities':[{'definition':'unit/review_hold','instanceAlias':'hold','position':{'row':1,'col':1}}]}}
    sim=Engine.create(Compiler().compile(data))
    sim.submit({'action':'skill','source':'hold','ability':'ability/review_hold'});sim.advance(1)
    before=sim.checkpoint()
    with pytest.raises(Exception) as failure:
        sim.ctx.abilities.interrupt('hold','review_fault',['ability/review_hold'])
    assert 'division' in str(failure.value).lower(),failure.value
    assert first_difference(before,sim.checkpoint()) is None
