from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter04_ranged_units import build
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[]


def fixture(kind,blocked=False,policy='table',distance=1):
    p=build(policy);unit=next(e for e in p['entities'] if kind in e['id'])
    p['entities'].append({'id':'unit/ranged_guard','kind':'entity','tags':['player'],'components':{
        'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},
        'attributes':{'base':{'max_hp':10000,'def':157,'mres':20,'block_count':1 if blocked else 0}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},
        'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']={'id':'scene/c4/ranged_probe','ruleset':'ruleset/ark_standard','objectives':{},
        'resources':{'dp':{'initial':20,'capacity':20}},
        'map':{'rows':3,'cols':7},'initialEntities':[{'definition':unit['id'],'instanceAlias':'enemy','position':{'row':1,'col':1}},
        {'definition':'unit/ranged_guard','instanceAlias':'guard','position':{'row':1,'col':1+distance}}]}
    if blocked:
        p['scenarioDraft']['initialEntities'].pop()
        p['scenarioDraft']['roster']=['unit/ranged_guard']
        p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,
            'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':6},'checkpoints':[]}
        enemy=p['scenarioDraft']['initialEntities'].pop()
        p['scenarioDraft']['waves']=[{'at':1,**enemy}]
    INPUTS.append(p);s=Engine.create(Compiler().compile(p),seed=74011)
    if blocked:s.submit({'action':'deploy','definition':'unit/ranged_guard','alias':'guard','position':{'row':1,'col':1}},at=0)
    return s


@pytest.mark.parametrize('kind,frame,damage',[('dcross',20,293),('wizard_2',19,240)])
def test_real_launch_frame_speed10_damage_and_saved_replay(kind,frame,damage,tmp_path):
    s=fixture(kind);s.advance(10);cp=tmp_path/'cp.json';sha=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,sha));s.advance(36);r.advance(36)
    starts=[e for e in s.session.events if e['type']=='ability.started'];launch=[e for e in s.session.events if e['type']=='projectile.launched'];hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(starts)==len(launch)==len(hits)==1
    assert launch[0]['time']==starts[0]['time']+frame
    assert hits[0]['payload']['amount']==damage and hits[0]['time']>launch[0]['time']
    assert s.ctx.resources.current('guard','hp')==10000-damage
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_dcross_after_actual_block_changes_to_direct_packet_on_shared_clock():
    s=fixture('dcross',blocked=True,distance=0);s.advance(135)
    starts=[e for e in s.session.events if e['type']=='ability.started'];hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(starts)==len(hits)==2 and starts[1]['payload']['ability'].endswith('/combat')
    assert starts[1]['time']-starts[0]['time']==90
    assert hits[1]['time']==starts[1]['time']+20 and hits[1]['payload']['amount']==293
    assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
    assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard')


def test_explicit_dcross_table2_2_vs_sourcecircle2_range_policy_changes_real_selection():
    source=fixture('dcross',policy='source_circle',distance=2.1);table=fixture('dcross',policy='table',distance=2.1)
    source.advance(2);table.advance(2)
    assert not [e for e in source.session.events if e['type']=='ability.started']
    assert len([e for e in table.session.events if e['type']=='ability.started'])==1
