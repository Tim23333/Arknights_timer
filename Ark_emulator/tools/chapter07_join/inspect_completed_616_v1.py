"""Verify actual fullprocess/disk/head without mutating the campaign registry."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'validation/campaign/chapter06_616_complete_inspection_v1'
FINAL = Path('E:/ArkSimEvidence/campaign/06_16_d509_normal_v4/full_v1.json')


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
    parent = ROOT / 'validation/campaign/chapter06_normal_join_v4/06-14.native.json'
    entry = {'package': 'validation/campaign/chapter06_normal_join_v4/06-14.life99999.json',
             'parent_package': parent.relative_to(ROOT).as_posix(), 'parent_sha256': sha(parent),
             'commands': 'scenarios/campaign/chapter06/level_main_06-14/public_plan_v4/commands.json',
             'implementation': 'd509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1',
             'report': copy.relative_to(ROOT).as_posix(), 'input_validation': 'native_life_overlay_v1'}
    result = inspect(ROOT, entry)
    assert result['process_status'] == 'complete' and result['determinism_status'] == 'verified' and result['durable_checkpoint_status'] == 'verified', result
    assert sum(final['actual_births'].values()) == 50 == final['state']['kills'] + final['state']['leaks']
    assert len(final['commands']) == 28 and final['journal']['events'] == 2722042
    assert sha(registry) == registry_before
    receipt = {'passed': True, 'entry': entry, 'inspection': result, 'actual_exit': 0,
               'actual_session_id': 36687, 'final_report_sha': sha(copy), 'registry_before_sha': registry_before,
               'registry_modified': False, 'formal_stage_registered': False,
               'scope': 'Actual originald509 completeprocess/durableCP/publichead; source numerical accuracy and client checks separate',
               'pending_model_gaps_from_original_manifest': final['pending_model_gaps']}
    target = OUT / 'inspection.json'
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'sha': sha(target), 'inspection': result}), flush=True)


if __name__ == '__main__':
    main()
