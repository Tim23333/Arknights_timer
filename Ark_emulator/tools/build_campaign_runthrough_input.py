"""Explicit base-life override for complete stage execution; unit HP unchanged."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def encoded(value): return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf8')


def apply(package, source_sha, life=99999):
    if type(life) is not int or life != 99999: raise ValueError('current user runthrough profile fixes base life99999')
    p = deepcopy(package); scene = p['scenarioDraft']; key = scene['objectives']['life_resource']
    if key not in scene['resources']: raise ValueError('explicit battle life resource required')
    native = deepcopy(scene['resources'][key])
    scene['resources'][key].update(initial=life, capacity=life)
    profile = {'id': 'campaign_full_process_base_life99999_v1', 'base_life_resource': key,
        'native_life_spec': native, 'override_initial': life, 'override_capacity': life,
        'unit_hp_unchanged': True, 'require_zero_leaks': False, 'require_squad_survival': False,
        'completion': 'all source wave actions executed; all enemy lifecycles terminal; pending0; timeline complete',
        'accuracy': 'intermediate data must match actual game; model assumptions/source-only evidence do not prove client correctness'}
    p['manifest']['metadata'].update(runthrough_profile=deepcopy(profile), runthrough_parent_sha256=source_sha,
        client_accuracy_verified=False, builder_sha256=sha(Path(__file__)))
    scene['metadata']['runthrough_profile'] = deepcopy(profile)
    p['manifest']['id'] += '/runthrough99999'; scene['id'] += '/runthrough99999'
    # Every definition, command, native wave, route, control, predefine and combat
    # formula remains byte-equivalent in its canonical JSON representation.
    for section in set(package)-{'manifest', 'scenarioDraft'}:
        if p[section] != package[section]: raise ValueError('runthrough changed unit/combat definitions')
    return p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--package', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    before = sha(args.package); p = apply(json.loads(args.package.read_bytes()), before)
    if args.check:
        if args.output.read_bytes() != encoded(p): raise ValueError('runthrough source/output drift')
    else: args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_bytes(encoded(p))
    assert sha(args.package) == before
    print(json.dumps({'parent_sha256': before, 'output_sha256': sha(args.output), 'base_life': 99999, 'unit_hp_unchanged': True, 'accuracy_verified': False}))
