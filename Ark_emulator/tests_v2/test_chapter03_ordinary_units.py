from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter03_ordinary_units import build
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


@pytest.mark.parametrize('name',['enemy_1000_gopro_2','enemy_1000_gopro_3','enemy_1006_shield_2','enemy_1033_handax','enemy_1033_handax_2','enemy_1032_katar','enemy_1014_rogue_2'])
def test_exact_variant_blocked_attack_actual_frames_and_damage(name,tmp_path):
    p=build();unit=next(u for u in p['entities'] if u['metadata']['native_reference']['id']==name)
    frame=unit['metadata'].get('OnAttack_frame');binding=next(r for r in p['manifest']['metadata']['variant_bindings'] if r['native_reference']['id']==name);frames=binding['OnAttack_frame'];frames=frames if isinstance(frames,list) else [frames]
    p['entities'].append({'id':'unit/test_blocker','kind':'entity','tags':['player'],'components':{'spatial':{},
        'attributes':{'base':{'max_hp':10000,'def':100,'mres':0,'block_count':1}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}}})
    p['scenarioDraft']={'id':'scene/test/c3ordinary','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},
        'roster':['unit/test_blocker'],'resources':{'dp':{'initial':10,'capacity':10}},
        'initialEntities':[{'definition':unit['id'],'instanceAlias':'enemy','position':{'row':0,'col':0},
            'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}]}
    s=Engine.create(Compiler().compile(p),seed=5310)
    s.submit({'action':'deploy','definition':'unit/test_blocker','alias':'blocker','position':{'row':0,'col':0}},at=0);s.advance(2)
    assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('blocker')
    cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    end=max(frames)+2;s.advance(end-2);r.advance(end-2)
    hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']
    atk=unit['components']['attributes']['base']['atk'];scale=.5 if len(frames)==2 else 1
    assert hits==[(f+1,max(atk*scale-100,atk*scale*.05)) for f in frames]
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_exact_db_level1_fly_source_no_attack_no_override1450():
    p=build();unit=next(u for u in p['entities'] if u['metadata']['native_reference']['id']=='enemy_1005_yokai')
    assert unit['components']['resources']['hp']['initial']==1870
    assert unit['metadata']['native_reference']['level']==1
    assert unit['components']['abilities']==[] and unit['components']['selection_state']['motion']==2
