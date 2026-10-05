"""Independent actual area counter against the declared native selector profile."""
import json
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.contracts import thaw
from tools.chapter10_gunctrl_v1.build import build, providers, BODY, P, SOURCE


def main():
    package = build()
    initial = [{'definition': BODY, 'instanceAlias': 'cannon', 'position': {'row': 0, 'col': 0}}]
    for name, side, ally_free, col in [('target', 0, False, 4), ('normal', 1, False, 5), ('free', 1, True, 6)]:
        key = 'unit/independent/cannon/' + name
        package['entities'].append({'id': key, 'kind': 'entity', 'tags': ['enemy'] if side else ['player'],
            'components': {'attributes': {'base': {'max_hp': 9917, 'atk': 0, 'def': 781, 'mres': 57, 'block_count': 3}},
                'resources': {'hp': {'role': 'health', 'initial': 9917, 'capacity': 9917}},
                'selection_state': {'side': side, 'motion': 1, 'category': 1, 'ally_target_free': ally_free},
                'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
        initial.append({'definition': key, 'instanceAlias': name, 'position': {'row': 5, 'col': col}})
    package['scenarioDraft'] = {'id': 'scene/independent/cannon_ally_free', 'ruleset': 'ruleset/ark_standard',
        'map': {'rows': 11, 'cols': 11}, 'resources': {'life': {'initial': 99999, 'capacity': 99999}},
        'initialEntities': initial, 'scheduledEffects': [{'at': 9, 'effect': {'op': 'modify_resource', 'target': 2, 'resource': 'sp', 'value': 120}}]}
    registry = providers()
    sim = Engine.create(Compiler(providers=registry).compile(package), providers=registry, seed=918347)
    sim.advance(12)
    raw = json.loads(SOURCE.read_bytes())
    config = next(c['raw'] for c in raw['projectiles']['projectile_gunctrl']['components'].values()
                  if c['native_class'] == 'AdvancedSelector')
    hp = {name: sim.ctx.resources.current(name, 'hp') for name in ('target', 'normal', 'free')}
    result = {'schema': 'ark-sim/gunctrl-independent-counter/v1', 'scope': 'Area selector only, not a whole stage',
        'source_configuration': config, 'source_absolute_side': 1, 'candidate_absolute_side': 1,
        'actual_ally_target_free': True, 'expected_HP': {'target': 6917, 'normal': 6917, 'free': 9917},
        'actual_HP': hp, 'counter_observed': hp == {'target': 6917, 'normal': 6917, 'free': 6917},
        'area_events': [thaw(e) for e in sim.session.events if e['type'] == 'area.resolved']}
    output = Path(__file__).resolve().parents[2] / 'validation/campaign/chapter10_gunctrl_peer_v1/counter.ally_free.v1.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    assert config['_ignoreAllyTargetFree'] == 0 and config['_targetSide'] == 3
    assert result['counter_observed']
    print(json.dumps({'actual_counter': True, 'actual_HP': hp}))


if __name__ == '__main__':
    main()
