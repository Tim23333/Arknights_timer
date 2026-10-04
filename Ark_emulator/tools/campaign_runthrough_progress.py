"""Inventory the life99999 goal separately from historical win receipts.

Only explicitly registered reports are inspected. Internal determinism and
client accuracy are different evidence; no boolean in a model report can
self-approve actual game accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def births(scene):
    counts = Counter()
    for wave in scene['timeline']['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                if action['kind'] == 'spawn':
                    counts[action['spawn']['definition']] += action.get('count', 1)
    return dict(counts)


def inspect(root, entry):
    """Validate persisted input identities and the explicit process criterion."""
    root = Path(root)
    row = {'process_status': 'not_run', 'determinism_status': 'pending',
           'durable_checkpoint_status':'pending','accuracy_status': 'pending', 'accuracy_reason': 'Independent actual-game comparison not registered'}
    report_path = root / entry['report']
    row['report'] = entry['report']
    if not report_path.exists():
        row.update(process_status='running_or_not_reported')
        return row
    try:
        package_path, commands_path = root / entry['package'], root / entry['commands']
        package, commands, report = load(package_path), load(commands_path), load(report_path)
        if report['schema']=='ark-sim/campaign-runthrough-failure/v1':
            if report['package_sha256']!=sha(package_path) or report['commands_sha256']!=sha(commands_path) or report['implementation']!=entry['implementation']:
                raise ValueError('Failure report input/runtime identity differs')
            if report['passed'] is not False or report['process_complete'] is not False:
                raise ValueError('Failure evidence cannot claim process completion')
            row.update(process_status='failed',failed_tick=report['failed_tick'],reason=report['error'],
                       report_sha256=sha(report_path),implementation=report['implementation'])
            return row
        if report['schema'] != 'ark-sim/campaign-runthrough/v1':
            raise ValueError('Unknown runthrough report schema')
        if report['package_sha256'] != sha(package_path) or report['commands_sha256'] != sha(commands_path):
            raise ValueError('Current package or command bytes differ from run evidence')
        if report['implementation'] != entry['implementation']:
            raise ValueError('Report implementation differs from registered runtime')
        if report['source_at_start'] != report['source_at_completion'] or report['identity_stable'] is not True:
            raise ValueError('Run did not preserve its source identity')
        scene = package['scenarioDraft']
        profile = scene['metadata']['runthrough_profile']
        key = profile['base_life_resource']
        if profile != report['profile'] or scene['resources'][key]['initial'] != 99999 or scene['resources'][key]['capacity'] != 99999:
            raise ValueError('Runthrough base life profile differs')
        parent_path = root / entry['parent_package']
        if package['manifest']['metadata']['runthrough_parent_sha256'] != sha(parent_path):
            raise ValueError('Parent package identity differs')
        from tools.build_campaign_runthrough_input import apply
        expected = apply(load(parent_path), sha(parent_path))
        # The builder identity is historical evidence. Rebuilding semantics
        # does not require its current source hash to equal an older run.
        expected['manifest']['metadata']['builder_sha256'] = package['manifest']['metadata']['builder_sha256']
        if expected != package:
            raise ValueError('Override changed data beyond base life and provenance')
        state = report['state']; expected_births = births(scene)
        if report['expected_births'] != expected_births:
            raise ValueError('Expected population differs from current source waves')
        # A bounded exploratory prefix legitimately leaves future commands
        # pending. Full-process proof still needs all registered outcomes.
        if len(report['commands']) > len(commands):
            raise ValueError('Recorded command outcomes exceed registered commands')
        if report['process_complete'] is True and len(report['commands']) != len(commands):
            raise ValueError('Not every scheduled public command has a recorded outcome')
        observed=list(report['commands'])
        expected_commands=sorted(enumerate(commands),key=lambda pair:(pair[1]['at'],pair[0]))
        if len(observed)>len(expected_commands):raise ValueError('Command population differs')
        for outcome,(_,registered) in zip(observed,expected_commands):
            action=dict(registered);tick=action.pop('at')
            if outcome.get('type') not in ('command.accepted','command.rejected') or outcome.get('time')!=tick or outcome.get('payload',{}).get('action')!=action:
                raise ValueError('Recorded command content/time differs from registered public command')
        if report.get('journal'):
            journal=report['journal'];path=Path(journal['path'])
            if not path.is_absolute():path=root/path
            if not path.exists() or sha(path)!=journal['sha256'] or journal['events']!=report['observations']['event_count']:
                raise ValueError('Complete event journal differs from streaming evidence')
        if report.get('durable_checkpoint_equal') is True:
            checkpoint=Path(report['checkpoint'])
            if not checkpoint.is_absolute():checkpoint=root/checkpoint
            if not checkpoint.exists() or sha(checkpoint)!=report['checkpoint_sha256']:
                raise ValueError('Durable checkpoint bytes differ from evidence')
            if report['checkpoint_encoding']!='insertion-order JSON; loaded from actual saved bytes':
                raise ValueError('Durable checkpoint encoding proof absent')
            row['durable_checkpoint_status']='verified'
        complete = (report['process_complete'] is True and state['finished'] is True
                    and state['pending_waves'] == 0 and state['timeline']['phase'] == 'complete'
                    and report['actual_births'] == expected_births
                    and state['kills'] + state['leaks'] == sum(expected_births.values())
                    and report['passed'] is True)
        row.update(process_status='complete' if complete else 'incomplete', report_sha256=sha(report_path),
                   implementation=report['implementation'], package_sha256=report['package_sha256'],
                   end_tick=report['end_tick'], kills=state['kills'], leaks=state['leaks'],
                   base_life_final=report['base_life_final'],
                   determinism_status='verified' if complete and report['checkpoint_equal'] is True and report['replay_equal'] is True else 'pending')
        # A future comparator needs native capture/version and field coverage
        # receipts. This inventory deliberately has no approval shortcut.
        if report.get('actual_game_accuracy_verified') is True:
            row['accuracy_reason'] = 'Model report claims accuracy; independent comparator receipt still required'
    except (KeyError, TypeError, ValueError, OSError) as error:
        row.update(process_status='stale_or_invalid', reason=str(error))
    return row


def build(root=ROOT):
    root = Path(root)
    catalog = load(root/'packages/campaign/mainline_catalog.json')
    registry_path = root/'validation/campaign/runthrough/registry.json'
    registry = load(registry_path)
    entries = registry['cases']
    targets = sorted((r for r in catalog['stages'] if r['selected']), key=lambda r: (r['chapter'], r['native_sequence']))
    target_ids = {r['native_id'] for r in targets}
    if set(entries) - target_ids:
        raise ValueError('Runthrough registry contains a case outside the fixed campaign')
    rows = []
    for target in targets:
        row = {'native_id': target['native_id'], 'code': target['code'], 'chapter': target['chapter'],
               'process_status': 'not_run', 'determinism_status': 'pending','durable_checkpoint_status':'pending', 'accuracy_status': 'pending'}
        if target['native_id'] in entries:
            row.update(inspect(root, entries[target['native_id']]))
        rows.append(row)
    policy_path=root/'validation/campaign/reference_first_policy_20261003.json'
    return {'schema': 'ark-sim/campaign-runthrough-progress/v1', 'goal_status': 'active',
            'base_life': 99999, 'unit_hp_unchanged': True,
            'delivery_policy':'reference-first full simulation; user actual-game feedback after delivery',
            'policy_sha256':sha(policy_path) if policy_path.exists() else None,
            'registry_sha256': sha(registry_path), 'catalog_sha256': sha(root/'packages/campaign/mainline_catalog.json'),
            'counts': {'targets': len(rows), 'process_complete': sum(r['process_status']=='complete' for r in rows),
                       'determinism_verified': sum(r['determinism_status']=='verified' for r in rows),
                       'durable_checkpoint_verified':sum(r['process_status']=='complete' and r['durable_checkpoint_status']=='verified' for r in rows),'actual_game_accuracy_verified': 0},
            'cases': rows, 'limitation': 'Reference-model delivery and later user client feedback are separate; no model report self-approves client accuracy'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'validation/campaign/runthrough/progress.json')
    args = parser.parse_args(); result = build(); args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps(result['counts']))
