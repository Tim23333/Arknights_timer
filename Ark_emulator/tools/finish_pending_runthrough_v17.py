"""Replay an already complete old-core run, preserving its passed CP proof.

Uses public Engine.create/Simulation.submit/Session.advance and immutable event
references. No runtime mutation, snapshot expansion, or old-core migration.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.campaign_streaming_evidence import observations, write_canonical, canonical_hash
from tools.campaign_ordered_checkpoint import load_bound, write_ordered


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024*1024), b''): digest.update(chunk)
    return digest.hexdigest()


def archive_failure(path, archive):
    pin = sha(path)
    if archive.exists():
        if sha(archive) != pin: raise ValueError('Existing failure archive differs; refusing overwrite')
    else:
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, archive)
    if sha(path) != pin or sha(archive) != pin: raise ValueError('Failure archive not byte exact')
    return {'source': str(path), 'archive': str(archive), 'sha256': pin}


def segmented_replay(program, record, step, progress=None):
    from ark_sim import Engine
    from ark_sim.tools.replay import _validated_record, ReplayError
    record = _validated_record(program, record)
    sim = Engine.create(program, seed=record['seed'], random_algorithm=record['random_algorithm'])
    if sim.runtime_fingerprint != record['runtime_fingerprint']:
        raise ReplayError('Replay runtime fingerprint differs')
    def advance_to(target):
        if target < sim.session.time: raise ReplayError('Replay submission/end precedes current clock')
        while sim.session.time < target:
            sim.session.advance(min(step, target-sim.session.time))
            if progress: progress(sim)
    for command in sorted(record['commands'], key=lambda c: c['order']):
        advance_to(command['submitted_at'])
        sim.submit(command['action'], at=command['at'])
    advance_to(record['until'])
    return sim


def small_case(program, original_record, report_path):
    """Actually execute legacy replay and a saved/reloaded CP at bounded size."""
    from ark_sim import Engine
    from ark_sim.tools.replay import replay
    record = json.loads(json.dumps(original_record))
    record['until'] = 20
    record['commands'] = record['commands'][:2]
    record['commands'][1]['submitted_at'] = 10
    forward = Engine.create(program, seed=record['seed'], random_algorithm=record['random_algorithm'])
    forward.submit(record['commands'][0]['action'], at=record['commands'][0]['at'])
    forward.session.advance(10)
    cp_path = report_path.with_suffix('.small.checkpoint.json')
    cp_sha = write_ordered(cp_path, forward.checkpoint())
    forward.submit(record['commands'][1]['action'], at=record['commands'][1]['at'])
    forward.session.advance(10)
    expected = observations(forward)
    # Bounded snapshot is the actual legacy comparison oracle in the small case.
    legacy_snapshot_hash = canonical_hash(forward.snapshot())
    restored = Engine.restore(program, load_bound(cp_path, cp_sha))
    restored.submit(record['commands'][1]['action'], at=record['commands'][1]['at'])
    restored.session.advance(10)
    cp_equal = expected == observations(restored)
    legacy = replay(program, record)
    legacy_equal = expected == observations(legacy)
    repeated = segmented_replay(program, record, 7)
    segmented_equal = expected == observations(repeated)
    result = {'schema': 'ark-sim/segmented-replay-small-proof/v17', 'record': record,
              'checkpoint': str(cp_path), 'checkpoint_sha256': cp_sha, 'observations': expected,
              'checkpoint_equal': cp_equal, 'legacy_replay_equal': legacy_equal,
              'segmented_replay_equal': segmented_equal, 'snapshot_hash_equal': expected['snapshot'] == legacy_snapshot_hash,
              'passed': cp_equal and legacy_equal and segmented_equal and expected['snapshot'] == legacy_snapshot_hash}
    write_canonical(report_path.with_suffix('.small.json'), result)
    del forward, restored, legacy, repeated
    gc.collect()
    if not result['passed']: raise ValueError('Actual v17 small-case proof failed')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime-root', type=Path, required=True)
    ap.add_argument('--case', required=True)
    ap.add_argument('--prior-report', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--step', type=int, default=200)
    ap.add_argument('--small-only', action='store_true')
    args = ap.parse_args()
    if args.step <= 0: raise ValueError('Positive segment required')
    args.output = args.output.resolve(); prior_path = args.prior_report.resolve()
    runtime = args.runtime_root.resolve(); sys.path.insert(0, str(runtime))
    import ark_sim
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    registry_path = ROOT/'validation/campaign/runthrough/registry.json'
    entry = json.loads(registry_path.read_bytes())['cases'][args.case]
    original_path = prior_path.with_suffix('.original.json')
    record_path = prior_path.with_suffix('.replay.json')
    original = json.loads(original_path.read_bytes()); prior = json.loads(prior_path.read_bytes())
    result = {'schema': 'ark-sim/persisted-original-replay-proof/v17', 'passed': False,
              'actual_game_accuracy_verified': False, 'formal_approved': False,
              'prior_report': str(prior_path), 'original_report': str(original_path), 'case': args.case}
    sim = None; started = time.monotonic(); phase = 'preflight'
    try:
        if Path(ark_sim.__file__).resolve().parent != runtime/'ark_sim' or implementation_digest() != entry['implementation']:
            raise ValueError('Wrong frozen old runtime')
        if not original['process_complete'] or original['implementation'] != entry['implementation']:
            raise ValueError('Original full run not complete under expected core')
        if prior.get('checkpoint_equal') is not True or prior.get('durable_checkpoint_equal') is not True:
            raise ValueError('Already passed actual durable checkpoint proof required')
        if not prior.get('identity_stable') or prior.get('recovery', {}).get('original_report_sha256') != sha(original_path):
            raise ValueError('Prior durable checkpoint proof is not bound to this original')
        result['previous_failure_archive'] = archive_failure(prior_path, args.output.with_suffix('.previous_failure.json'))
        source_start = original['source_at_start']
        if {p: sha(p) for p in source_start} != source_start: raise ValueError('Original source guard drift')
        package_path = ROOT/entry['package']; commands_path = ROOT/entry['commands']
        if sha(package_path) != original['package_sha256'] or sha(commands_path) != original['commands_sha256']:
            raise ValueError('Original input bytes drift')
        checkpoint_path = Path(original['checkpoint'])
        if not checkpoint_path.is_absolute(): checkpoint_path = ROOT/checkpoint_path
        if sha(checkpoint_path) != original['checkpoint_sha256']: raise ValueError('Passed CP source bytes drift')
        for p, pin in prior['recovery']['source_at_completion'].items():
            if sha(p) != pin: raise ValueError('Prior checkpoint source guard drift: '+p)
        journal = Path(original['journal']['path'])
        if not journal.is_absolute(): journal = ROOT/journal
        print(json.dumps({'phase': 'full_journal_sha_verification', 'bytes': journal.stat().st_size}), flush=True)
        if sha(journal) != original['journal']['sha256']: raise ValueError('Original full journal bytes drift')
        guards = [Path(__file__), original_path, record_path, prior_path, checkpoint_path, registry_path,
                  ROOT/'tools/campaign_streaming_evidence.py', ROOT/'tools/campaign_ordered_checkpoint.py']
        before = {str(p): sha(p) for p in guards}
        result.update(source_at_start=source_start, helper_guards_start=before,
                      core_start=implementation_digest(), original_sha256=sha(original_path),
                      original_journal=original['journal'], original_observations=original['observations'],
                      checkpoint_proof_reused={'path': str(prior_path), 'sha256': sha(prior_path),
                                               'checkpoint_sha256': original['checkpoint_sha256'], 'actual_equal': True},
                      forward_process_reused={'path': str(original_path), 'sha256': sha(original_path), 'actual_complete': True})
        package_bytes = package_path.read_bytes()
        program = Compiler().compile(json.loads(package_bytes))
        if program.fingerprint != original['program']: raise ValueError('Original program compilation drift')
        record = json.loads(record_path.read_bytes())
        if record['until'] != original['end_tick'] or record['seed'] != original['seed'] or record['runtime_fingerprint'] != original['runtime']:
            raise ValueError('Original replay clock/seed/runtime differs')
        phase = 'small_actual_checkpoint_and_replay'
        result['small_case'] = small_case(program, record, args.output)
        print(json.dumps({'phase': phase, 'passed': result['small_case']['passed']}), flush=True)
        if args.small_only:
            result['small_only'] = True
        else:
            phase = 'segmented_start_to_end_replay'
            def progress(value):
                print(json.dumps({'phase': phase, 'tick': value.session.time, 'target': record['until'],
                                  'events': len(value.session.events), 'elapsed_seconds': round(time.monotonic()-started, 2)}), flush=True)
            sim = segmented_replay(program, record, args.step, progress)
            phase = 'streaming_observation_hashes'
            print(json.dumps({'phase': phase, 'tick': sim.session.time, 'events': len(sim.session.events)}), flush=True)
            result['replay_observations'] = observations(sim)
            result['replay_equal'] = original['observations'] == result['replay_observations']
            result['replay_error'] = None
        result['source_at_completion'] = {p: sha(p) for p in source_start}
        result['helper_guards_completion'] = {str(p): sha(p) for p in guards}
        result['core_end'] = implementation_digest()
        result['identity_stable'] = result['source_at_completion'] == source_start and result['helper_guards_completion'] == before and result['core_end'] == result['core_start'] == entry['implementation']
        result['passed'] = bool(not args.small_only and result.get('replay_equal') and result['identity_stable'] and result['small_case']['passed'])
    except Exception as error:
        result['replay_error'] = {'phase': phase, 'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
        if sim is not None: result['failed_tick'] = sim.session.time
    finally:
        del sim
        gc.collect()
        result['elapsed_seconds'] = time.monotonic()-started
        result['actual_helper_exit'] = 0 if result['passed'] or (args.small_only and result.get('small_case', {}).get('passed') and result.get('identity_stable')) else 1
        write_canonical(args.output, result)
    print(json.dumps({'passed': result['passed'], 'replay_equal': result.get('replay_equal'), 'error': result.get('replay_error'), 'actual_helper_exit': result['actual_helper_exit']}), flush=True)
    raise SystemExit(result['actual_helper_exit'])


if __name__ == '__main__': main()
