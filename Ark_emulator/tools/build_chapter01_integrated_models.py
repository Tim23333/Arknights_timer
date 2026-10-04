"""Compose M21 stage inputs from three separately frozen feature packages."""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_chapter01_stage_models import encoded, sha

PINS = {
    'level_main_01-11': ('packages/campaign/chapter01_stage_models/m20_source/level_main_01-11.dormant.partial.json', '52a7432cc87e3806afd6d63c7a1fd2f06782caf34bdebde4cbc176b9ea7c7111'),
    'level_main_01-12': ('packages/campaign/chapter01_stage_models/m18/level_main_01-12.portal.partial.json', '6dc89b41ac24e81b0915ebc7dba98250ea3e03a0248dd2ee2af8146d3b1498e9'),
    'projectile': ('packages/campaign/chapter01_models/projectile_lifecycle/metadata_corrected/model.json', '09c06de158b44d25891ae38b3c58688a86eff9f9ded674b3d057f291b79d2133'),
}
CORE = 'c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e'
RUNTIME = ROOT.parent/'unpack_work/campaign_m21_integration_candidate'
OUT = ROOT/'packages/campaign/chapter01_stage_models/m21'


def build(level):
    path, pin = PINS[level]; projectile_path, projectile_pin = PINS['projectile']
    if sha(ROOT/path) != pin or sha(ROOT/projectile_path) != projectile_pin: raise ValueError('frozen feature input drift')
    stage = json.loads((ROOT/path).read_bytes()); module = json.loads((ROOT/projectile_path).read_bytes())
    for section in ('abilities', 'selectors', 'buffs', 'rules', 'projectiles'):
        rows = {item['id']: deepcopy(item) for item in stage.get(section, [])}
        # This is the complete frozen W module replacement. Other unit definitions
        # and stage movement/resources are preserved, rather than appended twice.
        for item in module.get(section, []): rows[item['id']] = deepcopy(item)
        stage[section] = [rows[key] for key in sorted(rows)]
    old = next(e for e in stage['entities'] if e['id'] == 'unit/chapter01_w')
    new = module['entities'][0]
    if new['id'] != old['id']: raise ValueError('W definition mapping changed')
    for attr, value in new['components']['attributes']['base'].items():
        if old['components']['attributes']['base'].get(attr) != value:
            raise ValueError('stage W attribute differs from the source projectile module: '+attr)
    old['components']['abilities'] = deepcopy(new['components']['abilities'])
    old.setdefault('metadata', {})['projectile_module'] = deepcopy(module['manifest']['metadata'])
    meta = stage['manifest']['metadata']; meta.update(required_runtime=CORE, builder_sha256=sha(Path(__file__)))
    meta['source_locks'].update({path: pin, projectile_path: projectile_pin})
    meta['pending_model_gaps'] = [gap for gap in meta['pending_model_gaps'] if gap != 'W_persistent_projectile_attachment_lifecycle']
    meta['pending_model_gaps'].append('new_combined_feature_runtime_and_stage_not_yet_reviewed')
    meta['model_profiles']['W_projectiles'] = deepcopy(module['manifest']['metadata']['projectile_lifecycle_profile'])
    stage['manifest']['id'] = 'package/campaign/chapter01_stage/'+level+'/m21'
    stage['scenarioDraft']['id'] = 'scenario/campaign/chapter01/'+level+'/m21'
    return stage


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/'ark_sim' or implementation_digest() != CORE: raise RuntimeError('wrong integrated runtime')
    OUT.mkdir(parents=True, exist_ok=True); results = []
    for level in ('level_main_01-11', 'level_main_01-12'):
        p = build(level); prog = Compiler().compile(p); output = OUT/(level+'.partial.json')
        if args.check:
            if output.read_bytes() != encoded(p): raise ValueError('integrated source input drift')
        else: output.write_bytes(encoded(p))
        results.append({'level': level, 'definitions': len(prog.definitions), 'sha256': sha(output), 'whole_stage': False})
    print(json.dumps({'implementation': CORE, 'stages': results}))
