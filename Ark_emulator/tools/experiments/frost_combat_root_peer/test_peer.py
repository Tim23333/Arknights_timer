import json
from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
ROOT=Path(__file__).resolve().parents[3]
BLAST='ability/frost/blast'


def scene():
    p=json.loads((ROOT/'packages/campaign/chapter04_boss/frost_combat_v6/first17.bb8.reference_ground.json').read_bytes())
    p['scenarioDraft']={'id':'scene/root_frost','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':5,'cols':7},
        'initialEntities':[{'definition':'unit/ch4/frstar/level0','instanceAlias':'boss','position':{'row':2,'col':2},
            'active':False,'registration_key':'frost'}]}
    return p


def test_dormant_initial_clock_is_relative_to_actual_activation_and_cp():
    s=Engine.create(Compiler().compile(scene()),seed=415)
    assert s.ctx.get('boss',('runtime','cooldowns'))=={}
    s.advance(17);s.ctx.lifecycle.activate_predefined('frost')
    assert s.ctx.get('boss',('runtime','cooldowns',BLAST))==272
    r=Engine.restore(s.program,s.checkpoint());s.advance(23);r.advance(23)
    assert s.checkpoint()==r.checkpoint()


def test_unpossessed_initial_override_cannot_create_partial_world_or_rng():
    s=Engine.create(Compiler().compile(scene()),seed=415);before=s.checkpoint()
    with pytest.raises(ValueError,match='possessed'):
        s.ctx.lifecycle.create('unit/ch4/frstar/level0',component_overrides={
            'ability_timing':{'initial_cooldowns':{'ability/missing':0}}})
    assert s.checkpoint()==before


def test_empty_qualified_primary_union_has_no_target_or_skill_packet():
    p=scene();p['scenarioDraft']['initialEntities'][0].pop('active');p['scenarioDraft']['initialEntities'][0].pop('registration_key')
    p['scenarioDraft']['initialEntities'][0]['components']={'ability_timing':{'initial_cooldowns':{BLAST:0}}}
    s=Engine.create(Compiler().compile(p),seed=415);s.advance(600)
    assert not any(e['type']=='ability.started' for e in s.session.events)
    assert not any(e['type']=='damage.accepted' for e in s.session.events)
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_instance_zero_override_used_after_dormant_activation():
    p=scene();p['scenarioDraft']['initialEntities'][0]['components']={'ability_timing':{'initial_cooldowns':{BLAST:0}}}
    s=Engine.create(Compiler().compile(p),seed=415);s.advance(37)
    s.ctx.lifecycle.activate_predefined('frost')
    assert s.ctx.get('boss',('runtime','cooldowns',BLAST))==37
