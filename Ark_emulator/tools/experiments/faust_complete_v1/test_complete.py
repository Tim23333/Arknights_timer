import json
from copy import deepcopy
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]
SUMMON='ability/ch5/faust/summon_ballis'


def fixture():
    p=json.loads((ROOT/'packages/campaign/chapter05_boss/faust/complete.v2.reference.json').read_bytes())
    branch=json.loads((ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json').read_bytes())
    # Actors only exercise source phase activation. Ballista mechanics have a
    # separate source consumer; this test does not pretend these tokens shoot.
    trap={'id':'unit/registered','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}}}}
    p['entities'].append(trap)
    item={'definition':'unit/ch5/faust/level0','instanceAlias':'boss','position':{'row':0,'col':0},
        'components':{'ability_timing':{'initial_cooldowns':{SUMMON:0}}}}
    p['scenarioDraft']={'id':'scene/faust_full','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':1,'cols':12},'rules':p['manifest']['metadata']['stage_rules'],
        'branches':{'faust_ballis':branch['program']},'initialEntities':[item]+[
        {'definition':'unit/registered','active':False,'registration_key':key,'instanceAlias':key,
            'position':{'row':0,'col':i+1}} for i,key in enumerate(branch['required_registrations'])]}
    return p


def test_actual_summon_priority_frame27_existing_activation_and_cp_replay():
    s=Engine.create(Compiler().compile(fixture()),seed=5510);s.advance(26)
    assert [e['payload']['ability'] for e in s.session.events if e['type']=='ability.started']==[SUMMON]
    r=Engine.restore(s.program,s.checkpoint());s.advance(30);r.advance(30)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert s.ctx.active('trap_007_ballis#1') and not s.ctx.active('trap_007_ballis#2')
    assert [e['time'] for e in s.session.events if e['type']=='entity.activated']==[27]
    assert s.ctx.get('boss',('runtime','next_attack'))==150
    assert s.ctx.get('boss',('runtime','cooldowns',SUMMON))==950
    assert s.ctx.branches.state()['faust_ballis']['cursor']==1


def test_exhausted_branch_rejects_summon_and_actor_targets_empty_no_rng():
    p=fixture();p['scenarioDraft']['branches']['faust_ballis']['phases']=[{'pre_delay_seconds':0,'actions':[]}]
    s=Engine.create(Compiler().compile(p),seed=5510);s.advance(55)
    assert s.ctx.branches.state()['faust_ballis']['cursor']==1
    before=s.checkpoint();s.ctx.abilities.tick(s.session);assert s.checkpoint()==before
    s.advance(1000)
    assert len([e for e in s.session.events if e['type']=='ability.started'])==1
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
