"""Extract the fixed twelve-person reachable module from frozen M26 content."""
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'
SOURCE_SHA = 'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'
OUT = ROOT / 'packages/campaign/roster/fixed12.m26.reference_module.json'


def build():
    from tools.campaign_content_composition import reachable_content
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Frozen fixed12 source drift')
    source = json.loads(raw); old = source.pop('scenarioDraft')
    scene = {key: deepcopy(old[key]) for key in ('ruleset', 'roster', 'rules', 'resources', 'parameters')}
    scene['id'] = 'scene/reference/fixed12_dependency_extraction'
    package, report = reachable_content(scene, [('frozen_m26_roster_source', source)],
        manifest_id='package/campaign_fixed12_reference_module')
    package.pop('scenarioDraft')
    package['manifest']['metadata'].update(
        source_locks={str(SOURCE.relative_to(ROOT)).replace('\\', '/'): SOURCE_SHA},
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        composition_helper_sha256=hashlib.sha256((ROOT/'tools/campaign_content_composition.py').read_bytes()).hexdigest(),
        roster=deepcopy(scene['roster']), stage_rules=deepcopy(scene['rules']),
        status='reachable fixed12 module; source/model policies inherited; no standalone battle scene',
        actual_client_verified=False,
        notes=['Names containing probe are retained when selected abilities actually reference them.',
               'Chapter1 enemies, predefined actors, devices and controls excluded by executable references.',
               'Inherited feedback/assumption records remain on original definitions.'])
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.runtime_root.resolve())); sys.path.insert(1, str(ROOT))
    import ark_sim
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()):
        raise ValueError('Explicit runtime not imported')
    result = build(); raw = (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes() != raw: raise ValueError('Fixed12 reachable module changed')
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_bytes(raw)
    print(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(), 'definitions':len(result['definitions']),
                      'roster_count':len(result['manifest']['metadata']['roster']), 'standalone_stage':False}))
