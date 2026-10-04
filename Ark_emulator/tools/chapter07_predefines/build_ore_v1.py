"""Actor-sourced ore skill consumer with declared finish timing policy."""
import hashlib
import json
from pathlib import Path
from ark_sim.domains.selection import DEFAULT_STATE

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'packages/campaign/chapter07_predefines/source.v4.reference.json'
RANGES = ROOT.parent / 'unpack_work/campaign_tables/range_table.reference_56a.json'
STEM = 'ch7/predefined/ore'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assert sha(SOURCE) == '9ab8b1049f5e0c9d34977563ccd8ac394044f77ff8da44b9cb717f52a1b9dfcb'
    assert sha(RANGES) == 'a98344d688a8933c4dd7ddaae3cb76c4347295359a18b60b918042cc2542d9d9'
    source = json.loads(SOURCE.read_bytes())
    skill = source['skill_tables']['sktok_ore']['levels'][0]
    raw = source['skill_prefabs']['sktok_ore']['components']
    action = next(v['raw'] for v in raw.values() if v['native_class'] == 'AnimatedActionToTargetAbility')
    config = raw[str(action['_selector']['m_PathID'])]['raw']
    ranges = json.loads(RANGES.read_bytes())['x-1']['grids']
    rule = 'rule/' + STEM
    buff = 'buff/' + STEM
    ability = 'ability/' + STEM + '/pulse'
    immune, listener = 'buff/ch7/source/ore_immune', 'buff/ch7/source/ore_listener'
    eligibility = {'rule': rule + '/eligibility', 'parameters': {
        'source_configuration': config, 'side_policy': 'relative_ally_enemy',
        'neutral_policy': 'absolute_mask', 'defaults': DEFAULT_STATE}}
    damage = {'op': 'damage', 'damage_type': 'true', 'scale': 0,
              'additions': skill['blackboard'][0]['value'],
              'damage_flags': {'source_attack_type': 'NONE', 'ignore_for_sp': False}}
    payloads = []
    for kind in ('damage', 'switch'):
        selected = buff + '/' + kind + '_payload'
        payloads.append({'op': 'buff_application', 'application_rule': rule + '/finish',
                         'allowed': [selected], 'parameters': {'mode': kind}})
    unit = {'id': 'unit/' + STEM + '/level1', 'kind': 'entity',
            'tags': ['device', 'native_ore'], 'components': {
        'attributes': {'base': {'max_hp': 100, 'atk': 0, 'def': 0, 'mres': 0,
                                'sp_recovery_rate': 1, 'move_speed': 1, 'block_count': 0}},
        'resources': {'hp': {'initial': 100, 'capacity': 100, 'role': 'health'},
                      'sp': {'initial': 0, 'capacity': 7, 'recovery_rate': 1,
                             'recovery': {'mode': 'periodic', 'interval_seconds': 1/30},
                             'parameters': {'freeze_cast_modes': ['manual'],
                                            'freeze_while_cast': True, 'pause_at_full': True}}},
        'selection_state': {'side': 2, 'category': 2, 'motion': 1, 'unit_type': 4},
        'spatial': {'motion_mode': 0, 'blocking': False}, 'abilities': [ability],
        'buffs': {'initial': [buff + '/passive']},
        'terrain_overlays': [{'key': 'native_ore_mode0', 'priority': 0,
                              'values': {'buildableType': 0, 'passableMask': 2,
                                         'physicalHeight': .4000000059604645},
                              'preserve': ['heightType', 'advancedBuildMask']}],
        'lifecycle': {'policy': 'policy/ark_lifecycle'}}}
    return {'schemaVersion': 2, 'manifest': {'id': 'package/' + STEM + '/v1',
        'requires': ['preset/ark_standard'], 'metadata': {
            'source_locks': {str(SOURCE): sha(SOURCE), str(RANGES): sha(RANGES),
                             str(Path(__file__).resolve()): sha(Path(__file__)),
                             str(Path(__file__).with_name('policies_v1.py')): sha(Path(__file__).with_name('policies_v1.py'))},
            'source_skill': 'sktok_ore', 'stage_export_allowed': False,
            'reference_policy': 'Ore active target Buff finish payloads emitted at fixed source preDelay, in source ore_s then ore_buff order; finish lifetime not recovered from native method body. Temporary durable payload marker performs conditional fixed packet or mode1 transition. No source-free damage or generic mine immunity.',
            'pending': ['Native active Buff finish lifetime and cancel handling calibration',
                        'considerUnhurtable=false interaction with unrelated invulnerability hooks',
                        'Separate mixed-version entity source', 'whole stage and independent review']}},
        'entities': [unit], 'selectors': [],
        'rules': [{'id': rule + '/eligibility', 'kind': 'rule', 'contract': 'targeting.eligibility',
                   'implementation': {'type': 'provider', 'provider': 'model.targeting.eligibility'}},
                  {'id': rule + '/area', 'kind': 'rule', 'contract': 'area.members',
                   'implementation': {'type': 'provider', 'provider': 'ark.area.qualified_cell_offsets'},
                   'parameters': {'offsets': [[g['row'], g['col']] for g in ranges],
                                  'eligibility': eligibility}},
                  {'id': rule + '/finish', 'kind': 'rule', 'contract': 'buff.application',
                   'implementation': {'type': 'provider', 'provider': 'reference.c7.ore_finish'},
                   'parameters': {'immune': immune, 'listener': listener,
                                  'damage': buff + '/damage_payload', 'switch': buff + '/switch_payload'}}],
        'buffs': [{'id': buff + '/passive', 'kind': 'buff',
                   'selection_flags': {'abnormal_flags': [5, 7]}},
                  {'id': buff + '/damage_payload', 'kind': 'buff', 'effects': [damage]},
                  {'id': buff + '/switch_payload', 'kind': 'buff',
                   'effects': [{'op': 'transition', 'state': 'mode1'}]}],
        'abilities': [{'id': ability, 'kind': 'ability',
                       'activation': {'mode': 'manual', 'costs': [{'resource': 'sp', 'amount': 7}],
                                      'parameters': {'auto_only': True, 'auto_when_ready': True,
                                                     'blocks_new_activations': True}},
                       'duration_seconds': 1.0,
                       'timeline': [{'at_seconds': action['_preDelay'],
                                     'effect': {'op': 'area', 'target': 'source', 'center': 'source',
                                                'membership_rule': rule + '/area', 'effects': payloads}}]}]}


def main():
    out = ROOT / 'packages/campaign/chapter07_predefines_consumer/ore.module.v1.json'
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + '\n').encode('utf8')
    assert not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(json.dumps({'sha256': sha(out), 'stage_export_allowed': False}))


if __name__ == '__main__':
    main()
