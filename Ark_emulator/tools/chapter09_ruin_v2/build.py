"""Native token044: ally SideType mask, blocking obstacle and passive immunity."""
from copy import deepcopy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / 'packages/campaign/chapter09_source_prepare/duruin.transitive.source.v1.json'
CLOSURE = ROOT / 'packages/campaign/chapter09_consumers/pillars/source.closure.v1.json'
PARENT = ROOT / 'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v2.life99999.json'
BODY = 'unit/ch9/pillar/ruin'
IMMUNITY = 'buff/ch9/ruin/immunity'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blocking(inputs, params, context):
    a = inputs['positions'][0]['blocker']; b = inputs['positions'][1]['target']
    distance_squared = (a['row']-b['row'])**2 + (a['col']-b['col'])**2
    return {'accepted': distance_squared < params['radius_squared'],
            'reason': 'source_ruin_block_radius_squared'}


def providers():
    from tools.chapter09_stage_assembly_v1.providers import providers as base
    return {**base(), 'reference.ch9.ruin_blocking': {'callable': blocking, 'version': 'native-squared-radius-v1'}}


def build():
    source = json.loads(SOURCE.read_bytes())
    components = source['native_prefab']['components'].values()
    root = next(c['raw'] for c in components if c['native_class'] == 'MapDependentTrap')
    inline = next(c['raw']['_buffs'][0] for c in components if c['native_class'] == 'PassiveBuffAbility')
    attributes = source['fixed56_character']['phases'][0]['attributesKeyFrames'][0]['data']
    assert root['_sideType'] == 1 and root['_category'] == 4
    assert inline['templateKey'] == 'immu_environment_damage' and not inline['loadFromDB']
    assert attributes['maxHp'] == 100 and attributes['blockCnt'] == 3
    parent = json.loads(PARENT.read_bytes())
    body = deepcopy(next(d for d in parent['definitions'] if d['id'] == BODY))
    body['tags'] = ['player', 'ground', 'ruin', 'terrain_mechanism']
    body['components']['selection_state']['side'] = {1: 0, 2: 1, 4: 2}[root['_sideType']]
    body['components']['buffs'] = {'initial': [IMMUNITY]}
    body['components']['deployable']['refund_ratio'] = root['_withdrawCostRecoverRatio']
    body['rules'] = {'blocking.eligibility': 'rule/ch9/ruin/blocking'}
    body['metadata'] = {'native_character': source['root'], 'native_side_mask': root['_sideType'],
                        'absolute_side_index': 0, 'entity_category': root['_category'],
                        'source_block_radius_squared': root['_blockRadiusSquare']}
    buff = {'id': IMMUNITY, 'kind': 'buff',
            'selection_flags': {'abnormal_flags': inline['attributes']['abnormalFlags'],
                                'abnormal_immunes': inline['attributes']['abnormalImmunes'],
                                'abnormal_combo_immunes': inline['attributes']['abnormalComboImmunes']},
            'damage_hooks': [{'phase': 'after', 'rule': 'rule/ch9/ruin/environment'}],
            'metadata': {'native_inline': inline,
                         'native_template': json.loads(CLOSURE.read_bytes())['closure']['templates']['immu_environment_damage']}}
    blocking = {'id': 'rule/ch9/ruin/blocking', 'kind': 'rule', 'contract': 'blocking.eligibility',
                'parameters': {'radius_squared': root['_blockRadiusSquare']},
                'implementation': {'type': 'provider', 'provider': 'reference.ch9.ruin_blocking'}}
    environment = {'id': 'rule/ch9/ruin/environment', 'kind': 'rule', 'contract': 'damage.pipeline',
                   'implementation': {'type': 'provider', 'provider': 'reference.ch9.demolition_environment'}}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/ch9/ruin/native_v2', 'metadata': {
        'source_locks': {str(p): sha(p) for p in (SOURCE, CLOSURE, PARENT, Path(__file__))},
        'side_mapping': 'Native SideType ALLY1 bitmask -> absolute SideTypeIndex ALLY0, never copy enum integer',
        'block_combat': 'Existing enemy combat selectors acquire actual player-tagged blocker; obstacle category4 prevents ordinary ranged selector acquisition',
        'source_native_stats': attributes, 'reference_url': 'https://prts.wiki/w/战场废墟',
        'visual_spawned_buff': 'Source 0.5s renderer changes have no gameplay effect; no lifetime fabricated',
        'client_verified': False}}, 'definitions': [body, buff, blocking, environment]}


def main():
    from tools.chapter09_demolition_v2.build import bind_status_definitions
    package = build()
    out = ROOT / 'packages/campaign/chapter09_consumers/ruin/module.v2.json'
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    stage = json.loads(PARENT.read_bytes())
    old = deepcopy(next(d for d in stage['definitions'] if d['id'] == BODY))
    stage['definitions'] = [d for d in stage['definitions'] if d['id'] != BODY] + deepcopy(package['definitions'])
    # The demolition push policy is bound to the complete final Buff closure.
    authored = {'buffs': [d for d in stage['definitions'] if d['kind'] == 'buff'],
                'rules': [d for d in stage['definitions'] if d['kind'] in ('rule', 'calculation_rule')]}
    bind_status_definitions(authored)
    stage['manifest']['metadata']['ruin_native_consumer'] = {
        'module_sha256': sha(out), 'parent_sha256': sha(PARENT), 'old_definition': old,
        'changes': ['SideType mask converted to absolute ally index', 'source immunity passive',
                    'source squared blocking radius', 'source withdrawal refund',
                    'player-ground combat tags with non-enemy wave accounting', 'complete final Buff map rebound'],
        'whole_stage_executed': False}
    path = PARENT.with_name('level_main_09-16.native_draft.v4.life99999.json')
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(stage, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'module_sha': sha(out), 'stage_sha': sha(path)}))


if __name__ == '__main__':
    main()
