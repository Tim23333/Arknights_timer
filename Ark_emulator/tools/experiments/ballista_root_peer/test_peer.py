import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3]


def fixture():
    p=json.loads((ROOT/'packages/campaign/chapter05_predefines/runtime_ballista/module.v2.reference.json').read_bytes())
    hero={'id':'unit/root_target','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':5000,'def':111,'mres':0}},
        'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},
        'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    p['entities'].append(hero);p['scenarioDraft']={'id':'scene/root_ballista','ruleset':'ruleset/ark_standard','objectives':{},
        'map':{'rows':3,'cols':7},'initialEntities':[{'definition':'unit/ch5/ballista/source_level6','instanceAlias':'caster',
            'position':{'row':1,'col':5},'facing':'left'},
            {'definition':'unit/root_target','instanceAlias':'far','position':{'row':1,'col':1}},
            {'definition':'unit/root_target','instanceAlias':'near','position':{'row':1,'col':4}}]}
    return p


def test_first_contact_geometry_precedes_actor_creation_order_single_hit_disk_replay(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=551);s.advance(155)
    pin=write_ordered(tmp_path/'before_hit.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'before_hit.json',pin))
    s.advance(65);r.advance(65)
    assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot()
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(hits)==1 and hits[0]['payload']['target']==s.session.world.resolve('near') and hits[0]['payload']['amount']==489
    assert s.ctx.resources.current('far','hp')==5000 and s.ctx.resources.current('near','hp')==4511
    assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1


@pytest.mark.parametrize('bad_state',[{'target_free':True},{'camouflage':True},{'side':1},{'category':4}])
def test_first_ineligible_does_not_consume_hit_quota_or_block_far(bad_state):
    p=fixture();p['scenarioDraft']['initialEntities'][2]['components']={'selection_state':bad_state}
    s=Engine.create(Compiler().compile(p),seed=551);s.advance(220)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(hits)==1 and hits[0]['payload']['target']==s.session.world.resolve('far') and hits[0]['payload']['amount']==489
    assert s.ctx.resources.current('near','hp')==5000


def test_source_spawn_dormant_has_no_charge_or_overlay_then_actual_activation_clock():
    p=fixture();p['scenarioDraft']['initialEntities'][0].update(active=False,registration_key='caster')
    s=Engine.create(Compiler().compile(p),seed=551);s.advance(100)
    assert s.ctx.resources.current('caster','sp')==0 and s.ctx.spatial.grid.tile(1,5)['buildableType']==1
    s.ctx.lifecycle.activate_predefined('caster');s.advance(220)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(hits)==1 and hits[0]['payload']['amount']==489
    assert s.ctx.spatial.grid.tile(1,5)['buildableType']==0 and s.ctx.spatial.grid.tile(1,5)['passableMask']==2
