"""New guarded revision evidence; preserve every prior accepted report."""
from pathlib import Path
import hashlib
import json
import sys
import uuid
import time
import tracemalloc

from revision_case import ROOT, RUNTIME, OUT, helper, case, sha


def manifest():
    roots = {
        'm71_python': RUNTIME/'ark_sim',
        'm68_python': ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate/ark_sim',
        'storage_tools': ROOT/'tools/candidates/m71_event_storage',
        'storage_experiments': ROOT/'tools/experiments/m71_event_storage'}
    result = {}
    for group, folder in roots.items():
        result[group] = {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*.py'))}
    result['consumed_catalog'] = {}
    # Include the complete frozen runtime JSON catalog and actual root package
    # consumed by this controlled scene. Per-run derived package is separately
    # bound in the evidence artifact manifest.
    for p in sorted((RUNTIME/'ark_sim').rglob('*.json')):
        result['consumed_catalog']['m71/'+str(p.relative_to(RUNTIME/'ark_sim'))] = sha(p)
    for p in [ROOT/'packages/custom/custom_guard.json', ROOT/'tools/campaign_ordered_checkpoint.py',
              ROOT/'tools/campaign_streaming_evidence.py',
              RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json']:
        result['consumed_catalog'][str(p)] = sha(p)
    return result


def core(mapping):
    return hashlib.sha256(json.dumps(mapping, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def main():
    before = manifest()
    assert core(before['m71_python']) == '15517b90969c61b15340929687092401b4a807b6a3f66d0d2135e780568c04aa'
    assert core(before['m68_python']) == '1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
    assert before['storage_tools']['campaign_streaming_evidence_v12.py'] == '91e041ac22515b4ed3c52f2a8d0a115c97d2ab0e105dd5c55b0c3b8658f828c3'
    OUT.mkdir(parents=True, exist_ok=True)
    run = OUT/('v13-'+uuid.uuid4().hex)
    run.mkdir()
    v13 = helper('campaign_streaming_evidence_v13.py')
    result = case(v13, run, 'v13')
    assert result['full_continuation_equal'], result
    assert result['resource_key_order_before'] == result['resource_key_order_after_reload'] == ['zeta', 'alpha']
    metadata = result['metadata']
    loaded = v13.load_checkpoint(metadata)
    assert loaded['kernel']['time'] == 3

    # Duplicate output must fail before creating another sealed journal copy.
    from ark_sim import Compiler, Engine
    original_path = Path(metadata['path'])
    original_bytes = original_path.read_bytes()
    package = json.loads((run/'v13-controlled-package.json').read_text(encoding='utf8'))
    sim = Engine.create(Compiler().compile(package), seed=123, event_journal_path=run/'duplicate-test-active.jsonl')
    sim.session.advance(63)
    # New benchmark measurements live entirely inside the start/end guards.
    # Keep all old benchmark/helper/report identities as their original evidence.
    from tools.campaign_streaming_evidence import observations as old_observations
    expected_observations = old_observations(sim)
    tracemalloc.start()
    started = time.perf_counter()
    actual_observations = v13.observations(sim, run/'guarded-benchmark-events.jsonl')
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert expected_observations == {key: actual_observations[key] for key in expected_observations}
    benchmark = {'scope': 'Complete controlled real ResourceSystem trace through tick63',
        'events': actual_observations['event_count'], 'export': actual_observations['export'],
        'seconds': elapsed, 'current_incremental_bytes': current, 'peak_incremental_bytes': peak,
        'canonical_full_observations_equal': True,
        'limits': 'Incremental Python allocation, not RSS, OS cache or fullstage acceptance'}
    sealed_before = sorted(run.glob('duplicate-test-active.jsonl.checkpoint-*'))
    try:
        v13.write_checkpoint(sim, original_path)
        raise AssertionError('Existing checkpoint was overwritten')
    except FileExistsError:
        pass
    assert original_path.read_bytes() == original_bytes
    assert sorted(run.glob('duplicate-test-active.jsonl.checkpoint-*')) == sealed_before

    # A publication race must preserve the race winner's bytes and remove staging.
    race = run/'publication-race.json'
    original_link = v13.os.link
    def competitor(source, target):
        Path(target).write_bytes(b'competitor evidence\n')
        original_link(source, target)
    v13.os.link = competitor
    try:
        try:
            v13.write_checkpoint(sim, race)
            raise AssertionError('Expected publication collision')
        except FileExistsError:
            pass
    finally:
        v13.os.link = original_link
    assert race.read_bytes() == b'competitor evidence\n'
    assert not list(run.glob('.*.tmp-*'))

    tampered = run/'tampered-main-checkpoint.json'
    tampered.write_bytes(original_bytes.replace(b'"time":3', b'"time":4', 1))
    try:
        v13.load_checkpoint({**metadata, 'path': str(tampered)})
        raise AssertionError('Tampered main checkpoint accepted')
    except ValueError:
        pass

    after = manifest()
    guards_equal = before == after
    report = {'schema': 'ark-sim/m71-final-storage-revision/v1', 'passed': guards_equal,
        'core': core(after['m71_python']), 'parent_core': core(after['m68_python']),
        'v12_reproduction': str(OUT/'v12-reproduction.json'), 'run': str(run), 'v13_case': result,
        'guarded_benchmark': benchmark,
        'checks': {'actual_ordered_checkpoint_reload_60ticks_fullvalues_equal': True,
            'duplicate_output_no_overwrite_or_extra_seal': True, 'atomic_publication_race_no_overwrite': True,
            'temporary_stage_removed': True, 'main_file_sha_tamper_rejected': True,
            'source_tools_consumed_catalog_start_end_equal': guards_equal},
        'start_manifest': before, 'end_manifest': after,
        'artifacts': {str(p.relative_to(run)): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in sorted(run.rglob('*')) if p.is_file()},
        'limits': ['Frozen M71 runtime unchanged', 'v12 checkpoint writer has reproduced order bug; retained as old evidence',
                   'v13 requires filesystem hard-link support; no fallback overwrite or fsync guarantee',
                   'Guard covers all runtime Python, complete runtime JSON catalog, storage tools, consumed custom package and old helpers; not unrelated root catalog',
                   'This controlled real ResourceSystem scene is not fullstage/36stage/client acceptance']}
    path = OUT/'final_revision_guarded.json'
    with path.open('x', encoding='utf8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write('\n')
    print(json.dumps({'path': str(path), 'passed': guards_equal, 'core': report['core'], 'case': result,
                      'checks': report['checks']}, ensure_ascii=False))
    assert guards_equal, 'Actual source/tools/consumed catalog changed during verification'

if __name__ == '__main__':
    main()
