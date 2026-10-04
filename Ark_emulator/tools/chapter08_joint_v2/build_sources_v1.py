"""Bind source consumers to the frozen joint runtime without changing source values."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v2_candidate'
CORE = 'a6ca7396556624768da2f83680ae34ad632d36dfa85f646916edbd1ee85f0128'
BASE = ROOT / 'packages/campaign/chapter08_consumers'
FIRE = BASE / 'boss/dragon_fire.module.v11.dynamic.json'
TALULA = BASE / 'boss/talula.dynamic.v8.reference.json'
FLAME = BASE / 'flame/module.v2.reference.json'
FIRE_OUT = BASE / 'boss/dragon_fire.module.v12.joint.json'
TALULA_OUT = BASE / 'boss/talula.dynamic.v9.joint.json'
FLAME_OUT = BASE / 'flame/module.v3.joint.json'
PINS = {
    FIRE: '3ebc2ad3a8c93629fd52d14b1ac0e85bb5047403f6088589bd5af3322d7af9e0',
    TALULA: '1cb0c01a461209d2ddd6cfb02eff9eab5687035799c30d4c672c7f18a6dde9ae',
    FLAME: 'ddb9686b18d559f9545592ebf55d016a6a3e3c46d922e6ba7f8ef51e480ae894',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if path.exists():
        assert path.read_bytes() == raw, 'Frozen source output differs: ' + str(path)
    else:
        path.write_bytes(raw)


def bind(source, source_id, fire=None):
    original = json.loads(source.read_bytes())
    result = deepcopy(original)
    if fire is not None:
        for group in ('rules', 'buffs'):
            ids = {row['id'] for row in fire[group]}
            result[group] = [row for row in result[group] if row['id'] not in ids] + deepcopy(fire[group])
    manifest = result['manifest']
    manifest['id'] = source_id
    meta = manifest['metadata']
    meta['required_runtime'] = CORE
    meta['source_locks'].update({str(source): sha(source), str(Path(__file__)): sha(Path(__file__))})
    if fire is not None:
        meta['source_locks'].update(fire['manifest']['metadata']['source_locks'])
        meta['source_locks'][str(FIRE_OUT)] = sha(FIRE_OUT)
        if 'burn_reference_policy' in meta:
            meta['burn_reference_policy'] = deepcopy(fire['manifest']['metadata']['reference_policy'])
    meta['joint_binding_scope'] = {
        'core': CORE, 'source_values_preserved': True,
        'dynamic_interval_policy': 'V8: sample historical time and attributes before pruning the last valid interval',
        'candidate_only': True, 'whole_stage_executed': False, 'client_verified': False,
    }
    # A new identity never upgrades the evidence belonging to its source parent.
    meta['source_gate_pending_for_this_identity'] = True
    for group in ('entities', 'abilities', 'projectiles', 'selectors', 'behaviors'):
        assert result.get(group) == original.get(group), group
    return result


def build():
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_buff_lifetime.talula_providers_v1 import providers as talula_providers
    from tools.chapter08_flame_device.policies_v1 import providers as flame_providers
    assert Path(ark_sim.__file__).resolve().is_relative_to(RUNTIME)
    assert implementation_digest() == CORE
    for path, expected in PINS.items():
        assert sha(path) == expected, str(path)
    fire = bind(FIRE, 'package/ch8/dragon_fire/joint_v12')
    write(FIRE_OUT, fire)
    talula = bind(TALULA, 'package/ch8/talula/joint_v9', fire)
    flame = bind(FLAME, 'package/ch8/flame/joint_v3', fire)
    for output, package, providers in ((TALULA_OUT, talula, talula_providers()),
                                       (FLAME_OUT, flame, flame_providers())):
        scene = deepcopy(package)
        scene['scenarioDraft'] = {
            'id': 'scene/joint/source_compile', 'ruleset': 'ruleset/ark_standard',
            'map': {'rows': 1, 'cols': 4},
            'initialEntities': [{'definition': package['entities'][0]['id'],
                                 'instanceAlias': 'source', 'position': {'row': 0, 'col': 0}}],
        }
        Compiler(providers=providers).compile(scene)
        write(output, package)
    return {'core': CORE, 'source_pins': {str(path): sha(path) for path in PINS},
            'outputs': {str(path): sha(path) for path in (FIRE_OUT, TALULA_OUT, FLAME_OUT)},
            'actual_compile': True, 'whole_stage_executed': False, 'client_verified': False}


if __name__ == '__main__':
    result = build()
    receipt = ROOT / 'validation/campaign/chapter08_joint_v2/source_bindings.v1.json'
    write(receipt, result)
    print(json.dumps(result, ensure_ascii=False))
