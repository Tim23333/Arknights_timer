"""Actual fixed-roster elemental packet silently lacks a receiver component."""
import json
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
ROOT = Path(__file__).resolve().parents[2]


def main():
    roster = json.loads((ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes())
    target = roster['manifest']['metadata']['roster'][0]
    package = {'schemaVersion': 2, 'definitions': roster['definitions'],
        'scenarioDraft': {'id': 'scene/elemental/fixed12_missing_receiver', 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 3, 'cols': 4}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
            'initialEntities': [{'definition': target, 'instanceAlias': 'operator', 'position': {'row': 1, 'col': 1}},
                                {'definition': 'unit/elemental/source', 'instanceAlias': 'source', 'position': {'row': 1, 'col': 3}}],
            'commands': [{'at': 5, 'action': 'skill', 'source': 'source', 'ability': 'ability/elemental/packet'}]}}
    package['definitions'] += [
        {'id': 'unit/elemental/source', 'kind': 'entity', 'tags': ['enemy'], 'components': {
            'attributes': {'base': {'max_hp': 5000, 'atk': 0, 'def': 0, 'mres': 0}},
            'resources': {'hp': {'role': 'health', 'initial': 5000, 'capacity': 5000}}, 'spatial': {},
            'selection_state': {'side': 1, 'category': 1, 'motion': 1}, 'abilities': ['ability/elemental/packet'],
            'lifecycle': {'policy': 'policy/ark_lifecycle'}}},
        {'id': 'selector/elemental/operator', 'kind': 'selector', 'region': {'type': 'all'},
         'filters': [{'field': {'path': ['definition_id'], 'equals': target}}, {'state': 'alive'}], 'limit': 1},
        {'id': 'ability/elemental/packet', 'kind': 'ability', 'activation': {'mode': 'manual'},
         'selector': 'selector/elemental/operator', 'timeline': [{'at': 0, 'effect': {
             'op': 'elemental_damage', 'element': 'DARK', 'amount': 113}}]}]
    sim = Engine.create(Compiler().compile(package), seed=1327)
    sim.advance(7)
    started = [thaw(e) for e in sim.session.events if e['type'] == 'ability.started' and e['payload']['ability'] == 'ability/elemental/packet']
    result = {'schema': 'ark-sim/fixed12-elemental-receiver-counter/v1', 'core': implementation_digest(),
        'actual_target_definition': target, 'actual_target_HP': sim.ctx.resources.current('operator', 'hp'),
        'actual_owned_packet_started': started, 'declared_receiver': thaw(sim.ctx.get('operator', ('elemental',))),
        'actual_elemental_state': thaw(sim.ctx.get('operator', ('runtime', 'elemental'))),
        'actual_elemental_events': [thaw(e) for e in sim.session.events if e['type'].startswith('elemental.')],
        'required_reference_receiver': {'capacity': 1000, 'expected_remaining_after113_without_recovery': 887},
        'scope': 'Actual missing fixed roster component; excludes whole-stage acceptance', 'client_verified': False}
    out = ROOT / 'validation/campaign/elemental_receivers_v1/primary.counter.v1.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    assert started and result['declared_receiver'] is None and result['actual_elemental_state'] is None
    print(json.dumps({'actual_missing_receiver': True, 'target': target}))


if __name__ == '__main__':
    main()
