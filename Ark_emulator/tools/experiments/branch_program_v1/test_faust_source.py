import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]


def test_actual_source_seven_phases_activate_all_ten_existing_registrations():
    source=json.loads((ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json').read_bytes())
    # Generic finite-health registered actors exercise scheduler activation.
    # This fixture does not claim the actual ballista attack consumer is ready.
    token={'id':'unit/registered','kind':'entity','components':{'attributes':{'base':{'max_hp':100}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}}}}
    request={'id':'ability/phase','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,
        'effect':{'op':'advance_branch','parameters':{'branch':source['branch_id']}}}]}
    actor={'id':'unit/actor','kind':'entity','components':{'abilities':['ability/phase']}}
    scene={'id':'scene/source_branch','ruleset':'ruleset/ark_standard','objectives':{},
        'branches':{source['branch_id']:source['program']},'initialEntities':[{'definition':'unit/actor','instanceAlias':'actor'}]+[
        {'definition':'unit/registered','active':False,'registration_key':key,'instanceAlias':key} for key in source['required_registrations']]}
    s=Engine.create(Compiler().compile(scene,packages=[{'definitions':[token,actor,request]}]),seed=50510)
    for i in range(7):s.submit({'action':'skill','source':'actor','ability':'ability/phase'},at=i*3)
    s.advance(9);r=Engine.restore(s.program,s.checkpoint());s.advance(14);r.advance(14)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    assert s.ctx.branches.state()['faust_ballis']['cursor']==7
    assert all(s.ctx.active(key) for key in source['required_registrations'])
    activations=[e for e in s.session.events if e['type']=='entity.activated']
    assert [e['payload']['registration_key'] for e in activations]==source['required_registrations']
    assert len([e for e in s.session.events if e['type']=='entity.created'])==11
