"""Canonical receiver shield integration, preserving both native SP gain sources."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HOOK = 'rule/m8_liskam_receiver_shield'
OUTPUTS = {
    'packages/campaign/squad.m8_damage.json': 'packages/campaign/squad.m8_roster.json',
    'packages/campaign/mainline_models/level_main_00-10.m8_damage.json': 'packages/campaign/mainline_models/level_main_00-10.m8_roster.json',
    'packages/campaign/mainline_models/level_main_00-11.m8_damage.json': 'packages/campaign/mainline_models/level_main_00-11.m8_roster.json',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source):
    from tools.build_chapter01_enemy_sources import bson_source
    source = Path(source)
    data = json.loads(source.read_bytes())
    recipe = json.loads((ROOT/'packages/campaign/skills.liskam.json').read_bytes())['manifest']['metadata']
    native = recipe['native_selected_skill']
    if native['skill_id'] != 'skchr_liskam_1' or native['level']['spData']['spType'] != 'INCREASE_WHEN_TAKEN_DAMAGE':
        raise ValueError('Liskam selected defense recovery source changed')
    bb = {r['key']: r['value'] for r in native['level']['blackboard']}
    if bb != {'def': 1, 'duration': 8} or native['level']['spData']['spCost'] != 18:
        raise ValueError('Liskam S1 model source differs')
    proof = bson_source({'damage_block_once'})
    if proof['missing_templates']:
        raise ValueError('native block template absent')
    nodes = proof['templates']['damage_block_once']['parsed']['eventToActions']['ON_TAKE_DAMAGE']
    if (len(nodes) != 2 or not nodes[0]['$type'].split(',')[0].endswith('+BlockDamage')
            or nodes[0]['_filterDamageType'] or nodes[0]['_filterApplyWay']
            or not nodes[1]['$type'].split(',')[0].endswith('+FinishBuff')):
        raise ValueError('unfiltered single-block native action source changed')
    unit = next(e for e in data['entities'] if e['id'] == 'unit/char_107_liskam')
    recovery = unit['components']['resources']['sp']['recovery']
    if recovery != {'amount': 1, 'event': 'damage.accepted', 'mode': 'event', 'owner_role': 'target'}:
        raise ValueError('Liskam base defense recovery differs from unpatched input')
    recovery['condition'] = 'inputs.event.amount > 0'
    talent = next(b for b in data['buffs'] if b['id'] == 'buff/talent_liskam_hit')
    subscription = talent['events'][0]
    if subscription['condition'] != 'inputs.payload.target == context.owner.id':
        raise ValueError('Liskam talent event condition differs from unpatched input')
    subscription['condition'] += ' and inputs.payload.amount > 0'
    shield = next(b for b in data['buffs'] if b['id'] == 'buff/liskam_def')
    if shield.get('damage_hooks') or any(r['id'] == HOOK for r in data['rules']):
        raise ValueError('canonical shield correction already applied')
    shield['damage_hooks'] = [{'phase': 'after', 'rule': HOOK, 'group': 'damage_block_charge', 'priority': 1000,
        'condition': 'inputs.target.components.resources.shield_charge.current > 0'}]
    data['rules'].append({'id': HOOK, 'kind': 'calculation_rule', 'contract': 'damage.pipeline',
        'implementation': {'type': 'graph', 'nodes': [{'id': 'blocked', 'expression':
            "{'accepted': True, 'amount': 0, 'allocations': [{'target': 'target', 'resource': 'shield_charge', 'amount': 1}], 'events': inputs.effect.settlement.events}"}],
            'output': 'nodes.blocked'}})
    manifest = data['manifest']
    manifest['id'] += '/roster1'; manifest['version'] += '.roster1'
    manifest['metadata']['m8_liskam_receiver_integration'] = {'input_path': str(source.relative_to(ROOT)),
        'input_sha256': sha(source), 'builder_sha256': sha(Path(__file__)),
        'native_recipe_sha256': sha(ROOT/'packages/campaign/skills.liskam.json'), 'native_block_template': proof,
        'SP_profile': 'base defense recovery1 + independent talent self1; adjacent ally talent1; no source removed',
        'damage_profile': 'all damage types receiver hook; one charge consumes one packet; DEF modifier remains8s',
        'blocked_event_profile': 'zero-health accepted packet spends charge, positive-health condition gates defense/talent SP',
        'client_pending': ['native BlockDamage/ON_TAKE_DAMAGE priority and SP event order', 'custom redirected allocation shield arbitration'],
        'formal_stage_approved': False, 'complete_operator': False, 'old_run_identity_is_not_reused': True}
    if 'scenarioDraft' in data:
        data['scenarioDraft']['id'] += '/roster1'
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    from ark_sim import Compiler
    for source, output in OUTPUTS.items():
        data = build(ROOT/source)
        if 'scenarioDraft' in data:
            program = Compiler().compile(data)
            print(json.dumps({'output': output, 'definitions': len(program.definitions), 'fingerprint': program.fingerprint}))
        path = ROOT/output
        if args.check:
            if not path.exists() or json.loads(path.read_bytes()) != data:
                raise SystemExit('M8 roster correction drift: '+output)
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
