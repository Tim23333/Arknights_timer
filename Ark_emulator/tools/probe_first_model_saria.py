"""Read-only integration witness: Saria's actual aura versus ordinary arts packet.

This copies the current stage into a bounded in-memory scene. It never modifies
the frozen package or issues an acceptance receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def probe(path):
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    data = json.loads(path.read_bytes())
    scene = data['scenarioDraft']
    scene.update(waves=[], scheduledEffects=[], objectives=[])
    scene.pop('timeline', None)
    for actor in data['entities']:
        if actor['id'] == 'unit/char_202_demkni':
            actor['components']['resources']['sp']['initial'] = 80
    scene['initialEntities'] = [
        {'definition': 'unit/char_202_demkni', 'instanceAlias': 'saria', 'position': {'row': 3, 'col': 3}},
        {'definition': 'unit/char_180_amgoat', 'instanceAlias': 'eyja', 'position': {'row': 3, 'col': 2}},
        {'definition': 'unit/audit_enemy', 'instanceAlias': 'victim', 'position': {'row': 3, 'col': 4}}]
    data['entities'].append({'id': 'unit/audit_enemy', 'kind': 'entity', 'tags': ['enemy', 'ground'],
        'components': {'attributes': {'base': {'max_hp': 10000, 'mres': 0, 'def': 0, 'move_speed': 1, 'arts_factor': 1}},
            'resources': {'hp': {'initial': 10000, 'capacity': 10000, 'role': 'health'}},
            'spatial': {}, 'lifecycle': {'policy': 'policy/ark_lifecycle'}}})
    sim = Engine.create(Compiler().compile(data), seed=73)
    source = sim.session.world.resolve('eyja')
    target = sim.session.world.resolve('victim')
    # Identical ordinary pipeline packets, no custom amplification rule injected.
    effect = {'op': 'damage', 'damage_type': 'arts', 'scale': 1}
    sim.ctx.effects.execute(source, [target], effect)
    before = [e['payload']['amount'] for e in sim.session.events if e['type'] == 'damage.accepted'][-1]
    sim.ctx.abilities.start('saria', 'ability/demkni_s3')
    factor = sim.ctx.attributes.value(target, 'arts_factor')
    sim.ctx.effects.execute(source, [target], effect)
    after = [e['payload']['amount'] for e in sim.session.events if e['type'] == 'damage.accepted'][-1]
    expected = before * factor
    return {'schema': 'ark-sim/first-model-integration-probe/v1', 'source_package': str(path),
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'implementation_digest': implementation_digest(),
        'program_fingerprint': sim.program.fingerprint, 'runtime_fingerprint': sim.runtime_fingerprint,
        'fixture': 'canonical Saria/Eyja copied unchanged except Saria SP80; MRES0 HP10000 bounded enemy; no waves',
        'before': before, 'factor': factor, 'after': after, 'independent_expected_after': expected,
        'amplification_observed': abs(after-expected) < 1e-8,
        'damage_events': [thaw(e) for e in sim.session.events if e['type'] == 'damage.accepted'],
        'formal_approval': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=ROOT/'packages/campaign/mainline_models/level_main_00-10.m7.json')
    parser.add_argument('--output', type=Path, default=ROOT/'validation/campaign/first_model_saria_integration_probe.json')
    args = parser.parse_args()
    result = probe(args.package.resolve())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k: result[k] for k in ('before','factor','after','independent_expected_after','amplification_observed')}))
