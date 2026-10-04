"""Verify actual fullprocess/disk/head without mutating the campaign registry."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'validation/campaign/chapter07_717_complete_inspection_v1'
FINAL = Path('E:/ArkSimEvidence/campaign/07_17_3992_native_draft_v2/full_v1.json')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    sys.path.insert(0, str(ROOT))
    from tools.campaign_runthrough_progress_v5 import inspect
    registry = ROOT / 'validation/campaign/runthrough/registry.json'
    registry_before = sha(registry)
    OUT.mkdir(exist_ok=False)
    copy = OUT / 'final.exact_copy.json'
    shutil.copyfile(FINAL, copy)
    assert sha(copy) == sha(FINAL)
    final = json.loads(copy.read_bytes())
    assert final['source_at_start'] == final['source_at_completion'] and final['identity_stable']
    for path, checksum in final['source_at_completion'].items():
        assert sha(Path(path)) == checksum, path
    parent = ROOT / 'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v2.json'
    entry = {'package': 'packages/campaign/chapter07_stage_models/level_main_07-15.native_draft.v2.life99999.strict_v2.json',
             'parent_package': parent.relative_to(ROOT).as_posix(), 'parent_sha256': sha(parent),
             'commands': 'scenarios/campaign/chapter07/level_main_07-15/public_plan_v2/commands.json',
             'implementation': '3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000',
             'report': copy.relative_to(ROOT).as_posix(), 'input_validation': 'native_life_public_dialogue_v1'}
    result = inspect(ROOT, entry)
    assert result['process_status'] == 'complete' and result['determinism_status'] == 'verified' and result['durable_checkpoint_status'] == 'verified', result
    assert sum(final['actual_births'].values()) == 37 == final['state']['kills'] + final['state']['leaks']
    assert len(final['commands']) == 28 and final['journal']['events'] == 2734457
    assert sha(registry) == registry_before
    receipt = {'passed': True, 'entry': entry, 'inspection': result, 'actual_exit': 0,
               'actual_session_id': 44582, 'final_report_sha': sha(copy), 'registry_before_sha': registry_before,
               'registry_modified': False, 'formal_stage_registered': False,
               'scope': 'Actual original3992 completeprocess/durableCP/publichead; source numerical accuracy and client checks separate',
               'pending_model_gaps_from_original_manifest': final['pending_model_gaps']}
    target = OUT / 'inspection.json'
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'sha': sha(target), 'inspection': result}), flush=True)


if __name__ == '__main__':
    main()
