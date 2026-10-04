"""Repair production Saria arts vulnerability through a receiver settlement hook."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HOOK = 'rule/m8_demkni_incoming_arts'
SCALE = 'rule/m8_demkni_settlement_scale'
OUTPUTS = {
    'packages/campaign/squad.integrated.json': 'packages/campaign/squad.m8_damage.json',
    'packages/campaign/mainline_models/level_main_00-10.m7.json': 'packages/campaign/mainline_models/level_main_00-10.m8_damage.json',
    'packages/campaign/mainline_models/level_main_00-11.m8.json': 'packages/campaign/mainline_models/level_main_00-11.m8_damage.json',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(data):
    data = deepcopy(data)
    native_path = ROOT/'packages/campaign/skills.demkni.json'
    native = json.loads(native_path.read_bytes())['manifest']['metadata']['native_selected_skill']
    bb = {r['key']: r['value'] for r in native['level']['blackboard']}
    multiplier = bb['demkni_s_3.damage_scale']
    if native['skill_id'] != 'skchr_demkni_3' or multiplier != 1.55:
        raise ValueError('Saria selected source identity changed')
    member = next(b for b in data['buffs'] if b['id'] == 'buff/demkni_member')
    if any(r['id'] in (HOOK, SCALE) for r in data['rules']) or member.get('damage_hooks'):
        raise ValueError('damage integration input already patched or conflicting')
    modifiers = {m['attribute']: m['value'] for m in member['modifiers']}
    if modifiers != {'move_speed': -.6, 'arts_factor': .55}:
        raise ValueError('Saria member aura differs from frozen source')
    member['damage_hooks'] = [{'phase': 'after', 'rule': HOOK, 'group': 'arts_damage_taken',
        'priority': multiplier-1, 'condition': "inputs.effect.damage_type == 'arts'"}]
    member.setdefault('metadata', {})['m8_production_damage_binding'] = True
    data['rules'] += [{'id': SCALE, 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
        'implementation': {'type': 'provider', 'provider': 'ark.damage.settlement_scale'}},
        {'id': HOOK, 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
         'parameters': {'source_bound_multiplier': multiplier}, 'implementation': {'type': 'graph', 'nodes': [
            {'id': 'scaled', 'rule': SCALE, 'inputs': {'source': 'inputs.source', 'target': 'inputs.target',
                'effect': "{'settlement':inputs.effect.settlement,'multiplier':params.source_bound_multiplier,'resource':inputs.effect.resource} if 'resource' in inputs.effect else {'settlement':inputs.effect.settlement,'multiplier':params.source_bound_multiplier}",
                'states': 'inputs.states', 'samples': 'inputs.samples'}}], 'output': 'nodes.scaled'}}]
    # Restore exact selected-skill identity fields using preserved native recipe
    # metadata. This changes review evidence, never selected skill mechanics.
    normalized_path = ROOT/'packages/campaign/operators.normalized.json'
    operators = {r['character_id']: r for r in json.loads(normalized_path.read_bytes())['operators']}
    for unit in data['entities']:
        meta = unit.get('metadata', {})
        if 'selected_skill_ability' not in meta:
            continue
        native_id = meta['native_id']
        row = operators[native_id]
        selected = row['selected_skill']['skill_id']
        if meta['config'] != row['config'] or meta['selected_skill_native_id'] != selected:
            raise ValueError('unit selected config differs from native normalized source')
        ability = next(a for a in data['abilities'] if a['id'] == meta['selected_skill_ability'])
        old = ability.setdefault('metadata', {}).get('native_skill_id')
        if old is not None and old != selected:
            raise ValueError('selected skill native identity conflicts with source')
        ability['metadata']['native_skill_id'] = selected
    manifest = data['manifest']
    manifest['id'] += '/m8_damage'
    manifest['version'] += '.damage1'
    manifest['metadata']['m8_damage_integration'] = {'native_skill_source': str(native_path.relative_to(ROOT)),
        'native_skill_source_sha256': sha(native_path), 'incoming_arts_multiplier': multiplier,
        'normalized_operator_source_sha256': sha(normalized_path),
        'binding': 'target aura member after hook; scales settlement and only target health allocations',
        'group_policy': 'highest priority arts_damage_taken hook; distinct fragility group multiplies independently',
        'legacy_arts_factor_retained_for_attribute_inspection': True, 'formal_stage_approved': False,
        'old_full_run_identity_is_not_reused': True}
    if 'scenarioDraft' in data:
        data['scenarioDraft']['id'] += '/m8_damage'
    return data


def build(source):
    source = Path(source)
    data = patch(json.loads(source.read_bytes()))
    data['manifest']['metadata']['m8_damage_input'] = {'path': str(source.relative_to(ROOT)), 'sha256': sha(source),
        'builder_sha256': sha(Path(__file__))}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    from ark_sim import Compiler
    for source, output in OUTPUTS.items():
        data = build(ROOT/source)
        # Squadron module needs an explicit scene; mainline wrappers retain one.
        if 'scenarioDraft' in data:
            program = Compiler().compile(data)
            print(json.dumps({'output': output, 'definitions': len(program.definitions), 'fingerprint': program.fingerprint}))
        path = ROOT/output
        if args.check:
            if not path.exists() or json.loads(path.read_bytes()) != data:
                raise SystemExit('M8 damage integration drift: '+output)
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
