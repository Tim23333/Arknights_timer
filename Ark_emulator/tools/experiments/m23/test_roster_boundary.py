"""Explicit scenario deck constrains public deployment, independently of owned spawns."""
from ark_sim import Compiler, Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay


def fixture():
    def unit(name):
        return {'id': 'unit/'+name, 'kind': 'entity', 'components': {
            'attributes': {'base': {'max_hp': 10, 'atk': 0, 'def': 0, 'mres': 0}},
            'resources': {'hp': {'initial': 10, 'capacity': 10, 'role': 'health'}}, 'spatial': {},
            'deployable': {'base_cost': 0, 'cooldown_seconds': 0, 'terrain': 'ground', 'capacity': 1}}}
    a, b = unit('card'), unit('predefined')
    return {'schemaVersion': 2, 'manifest': {'requires': ['preset/ark_standard']}, 'entities': [a, b],
        'scenarioDraft': {'id': 'scenario/deck_boundary', 'ruleset': 'ruleset/ark_standard', 'map': {'rows': 2, 'cols': 2},
            'roster': ['unit/card'], 'resources': {'dp': {'initial': 10, 'capacity': 20}}, 'objectives': {},
            'initialEntities': [{'definition': 'unit/predefined', 'instanceAlias': 'npc', 'position': {'row': 1, 'col': 1},
                'active': False, 'registration_key': 'native-npc'}]}}


def test_public_deploy_rejects_loaded_predefined_definition_outside_selected_roster():
    sim = Engine.create(Compiler().compile(fixture()), seed=2301)
    sim.submit({'action': 'deploy', 'definition': 'unit/predefined', 'alias': 'illegal', 'position': {'row': 0, 'col': 0}}, at=0)
    sim.advance(1)
    rejected = [e for e in sim.session.events if e['type'] == 'command.rejected']
    assert len(rejected) == 1 and 'roster' in rejected[0]['payload']['reason']
    assert len([e for e in sim.session.world.entities() if e['definition_id'] == 'unit/predefined']) == 1
    assert sim.ctx.resources.current('system/battle', 'dp') == 10
    assert first_difference(sim.snapshot(), replay(sim.program, sim.export_replay()).snapshot()) is None


def test_explicit_empty_roster_rejects_deployment_while_absent_roster_keeps_open_authoring():
    p = fixture(); p['scenarioDraft']['roster'] = []
    sim = Engine.create(Compiler().compile(p))
    sim.submit({'action': 'deploy', 'definition': 'unit/predefined', 'position': {'row': 0, 'col': 0}}, at=0); sim.advance(1)
    assert len([e for e in sim.session.events if e['type'] == 'command.rejected']) == 1
    p['scenarioDraft'].pop('roster'); sim = Engine.create(Compiler().compile(p))
    sim.submit({'action': 'deploy', 'definition': 'unit/predefined', 'position': {'row': 0, 'col': 0}}, at=0); sim.advance(1)
    assert len([e for e in sim.session.events if e['type'] == 'command.accepted']) == 1

