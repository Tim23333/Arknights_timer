"""Compose frozen visual ownership with the source75k four-mode Boss."""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_campaign_foundation_v5_candidate'
CORE = '82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
BASE = ROOT / 'packages/campaign/chapter08_consumers/bsnake'
PARENT = BASE / 'four_modes.wave_source.v5.json'
VISUAL = BASE / 'visual.module.v3.json'
OUT = BASE / 'four_modes.visual_source.v6.json'


def sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    from ark_sim.adapters.api import implementation_digest
    from tools.campaign_content_composition_v2 import compose_modules
    assert implementation_digest() == CORE
    assert sha(PARENT) == '944c66226964c3eac64f6e00295e37839489a12da378377724e34f43cbe67613'
    assert sha(VISUAL) == '11f20921c8c150841846d693e49531fa4828acd759cd45beb8a0a3a5cec25343'
    parent = json.loads(PARENT.read_bytes())
    visual = json.loads(VISUAL.read_bytes())
    owner = visual['manifest']['metadata']['owner']
    before = next(row for row in parent['definitions'] if row['id'] == owner)
    entity = deepcopy(before)
    body = entity['components']
    metadata = visual['manifest']['metadata']
    body['buffs']['initial'] += metadata['initial_owned_buffs']
    body['rebirth']['retain_buffs'] = list(dict.fromkeys(
        body['rebirth']['retain_buffs'] + metadata['rebirth_retained_buffs']))
    terminal = body['rebirth']['zero_restore_lifecycle']
    terminal['retained_buffs'] = list(dict.fromkeys(
        terminal['retained_buffs'] + metadata['terminal_retained_buffs']))
    definitions, provenance = compose_modules([('source_four_modes', parent), ('source_visual', visual)])
    definitions[owner] = entity
    assert body['attributes'] == before['components']['attributes']
    assert body['resources'] == before['components']['resources']
    assert body['abilities'] == before['components']['abilities']
    assert body['ability_arbitration'] == before['components']['ability_arbitration']
    result = deepcopy(parent)
    result['definitions'] = list(definitions.values())
    result['manifest']['id'] = 'package/ch8/bsnake/four_modes_visual_source_v6'
    meta = result['manifest']['metadata']
    meta['required_runtime'] = CORE
    meta['source_locks'].update(metadata['source_locks'])
    meta['source_locks'].update({str(path): sha(path) for path in (PARENT, VISUAL, Path(__file__))})
    meta['visual_join'] = {
        'visual_module_sha': sha(VISUAL), 'original_stats_resources_abilities_preserved': True,
        'added_ownership': deepcopy(metadata), 'provenance': provenance,
        'actual_joint_validation_pending': True, 'renderer_rendered': False,
        'whole_stage_executed': False, 'client_verified': False,
    }
    return result


if __name__ == '__main__':
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    result = build()
    assert not OUT.exists()
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'sha': sha(OUT), 'core': CORE, 'definitions': len(result['definitions']),
                      'source_values_preserved': True, 'whole_stage': False}))
