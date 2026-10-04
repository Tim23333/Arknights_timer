"""Register originald509 completeprocess; source and client accuracy remain separate."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sys.path.insert(0, str(ROOT))
    path = ROOT / 'validation/campaign/chapter06_616_complete_inspection_v1/inspection.json'
    assert sha(path) == 'f5fa9808da2d7056f7b64fc66010507f66afdf2f8ca008c1b6c0b26b6c96a90d'
    proof = json.loads(path.read_bytes())
    assert proof['passed'] and proof['actual_exit'] == 0 and proof['actual_session_id'] == 36687
    final_path = ROOT / proof['entry']['report']
    assert sha(final_path) == proof['final_report_sha'] == '6404708c7599a707a345e1c8fdb83a4cf723ebc96d584624d3f240d71f350b99'
    final = json.loads(final_path.read_bytes())
    assert final['source_at_start'] == final['source_at_completion']
    for name, expected in final['source_at_completion'].items():
        assert sha(name) == expected, name
    scene = json.loads((ROOT / proof['entry']['package']).read_bytes())
    for name, expected in scene['manifest']['metadata']['source_locks'].items():
        source = Path(name)
        if not source.is_absolute():
            source = ROOT / source
        assert sha(source) == expected, str(source)
    assert scene['manifest']['metadata']['required_core'] == final['implementation']
    controls = [row for row in scene['definitions'] if row['kind'] == 'control']
    assert len(controls) == 1 and controls[0]['ack_policy'] == 'immediate'
    assert not [step for control in controls for step in control['steps'] if step['kind'] != 'effects']
    assert sum(final['actual_births'].values()) == 50 == final['state']['kills'] + final['state']['leaks']
    deployed = [command for command in final['commands'] if command['type'] == 'command.accepted'
                and command['payload']['action']['action'] == 'deploy']
    assert len({command['payload']['action']['entity'] for command in deployed}) == 12
    registry = ROOT / 'validation/campaign/runthrough/registry.json'
    before = registry.read_bytes()
    assert hashlib.sha256(before).hexdigest() == proof['registry_before_sha']
    current = json.loads(before)
    assert 'main_06-14' not in current['cases']
    out = ROOT / 'validation/campaign/runthrough/register_06_16_source_v1'
    out.mkdir(exist_ok=False)
    (out / 'registry.before.json').write_bytes(before)
    current['cases']['main_06-14'] = proof['entry']
    registry.write_text(json.dumps(current, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    receipt = {'passed': True, 'native_id': 'main_06-14', 'display': '6-16', 'entry': proof['entry'],
               'inspection_sha': sha(path), 'registry_before_sha': hashlib.sha256(before).hexdigest(),
               'registry_after_sha': sha(registry), 'births': 50, 'kills': 15, 'leaks': 35,
               'base_life_final': 99963, 'public_player_deployments': 12, 'events': 2722042,
               'scope': 'Actual originald509 reference completeprocess/durableCP/head; source numeric consumer evidence and user feedback separate',
               'actual_game_accuracy_verified': False, 'no_public_ack_controls': True}
    (out / 'registration.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'sha': sha(out / 'registration.json'), 'progress_rebuild_pending': True}), flush=True)
    from tools.campaign_runthrough_progress_v5 import build
    progress = build(ROOT)
    assert progress['counts']['process_complete'] == progress['counts']['determinism_verified'] == progress['counts']['durable_checkpoint_verified'] == 12
    (out / 'progress.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'counts': progress['counts'], 'progress_sha': sha(out / 'progress.json')}), flush=True)


if __name__ == '__main__':
    main()
