"""Register original3992 completeprocess after actual triplejournal inspection."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sys.path.insert(0, str(ROOT))
    inspection = ROOT / 'validation/campaign/chapter07_717_complete_inspection_v2/inspection.json'
    assert sha(inspection) == '536f0a9b30c92c9e9c9815bbbc168449fd6690e70cbbec7ac2c4b3eeb7859d73'
    proof = json.loads(inspection.read_bytes())
    assert proof['passed'] and proof['actual_exit'] == 0 and proof['actual_session_id'] == 44582
    final_path = ROOT / proof['entry']['report']
    assert sha(final_path) == proof['final_report_sha'] == '4433b347fb554b9ce9d8bea7f6a4de5912a32116c71832ee64dd4f78c4c7de58'
    final = json.loads(final_path.read_bytes())
    assert final['source_at_start'] == final['source_at_completion']
    for path, expected in final['source_at_completion'].items():
        assert sha(Path(path)) == expected, path
    source_path = ROOT / 'validation/campaign/chapter07_inputs_admission_peer_v1/freeze.json'
    assert sha(source_path) == 'c170cb713c4563fd8ae395800259b2cf3607606d4c7d85b3a157f8c4093224f3'
    source = json.loads(source_path.read_bytes())
    stage = next(row for row in source['stages'] if row['display'] == '7-17')
    assert source['passed'] and stage['admitted_reference_profile'] and not stage['unsupported_required_source_field_confirmed']
    assert stage['source_package_sha'] == proof['entry']['parent_sha256'] and stage['lifeoverlay_sha'] == final['package_sha256']
    assert stage['commands_sha'] == final['commands_sha256']
    scene = json.loads((ROOT / proof['entry']['package']).read_bytes())
    controls = [row for row in scene['definitions'] if row['kind'] == 'control']
    assert len(controls) == 1 and controls[0]['ack_policy'] == 'immediate'
    assert not [step for control in controls for step in control['steps'] if step['kind'] != 'effects']
    registry = ROOT / 'validation/campaign/runthrough/registry.json'
    before = registry.read_bytes()
    assert hashlib.sha256(before).hexdigest() == proof['registry_before_sha']
    current = json.loads(before)
    assert 'main_07-15' not in current['cases']
    out = ROOT / 'validation/campaign/runthrough/register_07_17_source_v1'
    out.mkdir(exist_ok=False)
    (out / 'registry.before.json').write_bytes(before)
    current['cases']['main_07-15'] = proof['entry']
    registry.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    receipt = {'passed': True, 'native_id': 'main_07-15', 'display': '7-17', 'entry': proof['entry'],
               'inspection_sha': sha(inspection), 'source_admission_sha': sha(source_path),
               'registry_before_sha': hashlib.sha256(before).hexdigest(), 'registry_after_sha': sha(registry),
               'births': 37, 'kills': 26, 'leaks': 11, 'events': 2734457,
               'no_public_ack_controls': True, 'actual_game_accuracy_verified': False,
               'scope': 'Actual original3992 reference fullprocess/durableCP/head. Standardformula audit separate; 114 remaining numeric categories not claimed verified.'}
    (out / 'registration.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'registration_sha': sha(out / 'registration.json'),
                      'registry_sha': sha(registry), 'progress_rebuild_pending': True}), flush=True)
    from tools.campaign_runthrough_progress_v5 import build
    progress = build(ROOT)
    assert progress['counts']['process_complete'] == progress['counts']['determinism_verified'] == progress['counts']['durable_checkpoint_verified'] == 11
    (out / 'progress.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'counts': progress['counts'], 'progress_sha': sha(out / 'progress.json')}), flush=True)


if __name__ == '__main__':
    main()
