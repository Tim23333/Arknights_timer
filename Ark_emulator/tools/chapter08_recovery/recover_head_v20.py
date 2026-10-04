"""Recover the missing head proof of an interrupted frozen V18 run.

Original terminal and checkpoint proofs remain immutable. New head journals
and resumable head checkpoints live exclusively under the fixed log root.
"""
import argparse
from collections import Counter
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prior', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    a = p.parse_args()
    log_root = Path('E:/ArkSimLogs/runs').resolve()
    run_dir = a.run_dir.resolve()
    if not run_dir.is_relative_to(log_root):
        raise ValueError('All new raw logs must remain within the fixed root')
    if a.output.exists() or run_dir.exists():
        raise FileExistsError('Preserve prior attempts')
    d = json.loads(a.prior.read_bytes())
    original_sources = d['source_at_start']
    for path, expected in original_sources.items():
        if sha(path) != expected:
            raise ValueError('Original source drift: ' + path)
    if not (d['process_complete'] and d['checkpoint_equal'] and
            d['durable_checkpoint_equal'] and d['driver_equal']):
        raise ValueError('Original terminal/checkpoint proof incomplete')
    runtime = Path(d['runtime_module']).resolve().parents[1]
    sys.path.insert(0, str(runtime))
    import ark_sim
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import _validated_record
    from tools.campaign_streaming_evidence import write_canonical
    if Path(ark_sim.__file__).resolve().parent != runtime / 'ark_sim':
        raise ValueError('Wrong runtime loaded')
    if implementation_digest() != d['implementation']:
        raise ValueError('Original implementation drift')
    package_path = next(Path(x) for x in original_sources if 'native_draft' in x)
    provider_path = next(Path(x) for x in original_sources
                         if 'runner_' in Path(x).name and 'providers' in Path(x).name)
    helper_path = next(Path(x) for x in original_sources
                       if Path(x).name == 'campaign_streaming_evidence_v14.py')
    providers = load_module('selected_recovery_providers', provider_path).providers()
    helper = load_module('selected_recovery_evidence', helper_path)
    package = json.loads(package_path.read_bytes())
    scene = package['scenarioDraft']
    life = scene['metadata']['runthrough_profile']['base_life_resource']
    if scene['resources'][life]['initial'] != 99999 or scene['resources'][life]['capacity'] != 99999:
        raise ValueError('Base life overlay drift')
    program = Compiler(providers=providers).compile(package)
    if program.fingerprint != d['program']:
        raise ValueError('Compiled program drift')
    replay_path = a.prior.with_name(a.prior.name.replace('.checkpoint_result.json', '.replay.json'))
    record = _validated_record(program, json.loads(replay_path.read_bytes()))
    if record['runtime_fingerprint'] != d['runtime'] or record['until'] != d['end_tick']:
        raise ValueError('Replay identity/end drift')
    checkpoint = {'path': d['checkpoint'], 'sha256': d['checkpoint_sha256'],
                  'event_reference': d['checkpoint_event_reference']}
    if sha(checkpoint['path']) != checkpoint['sha256']:
        raise ValueError('Saved original checkpoint drift')
    restored = Engine.restore(program, helper.load_checkpoint(checkpoint), providers=providers)
    if restored.runtime_fingerprint != d['runtime']:
        raise ValueError('Restored original runtime drift')
    if d['public_dialogue_driver']:
        from tools.control_driver.public_ack_v2 import PublicAckDriver
        cp_driver = d['driver_checkpoint']
        if sha(cp_driver['path']) != cp_driver['sha256']:
            raise ValueError('Saved external STORY driver drift')
        restored_driver = PublicAckDriver(restored, json.loads(Path(cp_driver['path']).read_bytes()))
        if restored_driver.checkpoint()['at'] != restored.session.time:
            raise ValueError('Saved driver clock differs from CP')
    del restored
    gc.collect()
    # Authenticate both full existing journal files before reusing their proof.
    for key in ('journal', 'continuation_journal'):
        entry = d[key]
        if sha(entry['path']) != entry['sha256'] or Path(entry['path']).stat().st_size != entry['bytes']:
            raise ValueError('Original ' + key + ' bytes drift')
    if d['journal']['sha256'] != d['continuation_journal']['sha256']:
        raise ValueError('Original disk continuation differs')
    sources = dict(original_sources)
    sources[str(a.prior.resolve())] = sha(a.prior)
    sources[str(replay_path.resolve())] = sha(replay_path)
    sources[str(Path(__file__).resolve())] = sha(__file__)
    # Bind every loaded provider/import dependency in addition to the original
    # callable-source guard and full implementation digest.
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and (path.is_relative_to(ROOT / 'tools') or path.is_relative_to(runtime / 'ark_sim')):
                sources[str(path)] = sha(path)
    run_dir.mkdir(parents=True)
    write_canonical(run_dir / 'source_guard.json', sources)
    result = dict(d)
    result['recovery'] = {'schema': 'ark-sim/missing-head-recovery/v20',
                          'prior': str(a.prior.resolve()), 'prior_sha256': sha(a.prior),
                          'original_forward_reused': True, 'original_cp_reused': True,
                          'old_interrupted_replay_preserved': True,
                          'source_at_recovery_start': sources}
    sim = Engine.create(program, providers=providers, seed=record['seed'],
                        random_algorithm=record['random_algorithm'],
                        event_journal_path=run_dir / 'head.active.jsonl')
    if sim.runtime_fingerprint != d['runtime']:
        raise ValueError('Head runtime drift')
    ordered = sorted(record['commands'], key=lambda x: x['order'])
    cursor = 0
    head_cp = None
    while sim.session.time < record['until']:
        while cursor < len(ordered) and ordered[cursor]['submitted_at'] == sim.session.time:
            command = ordered[cursor]
            sim.submit(command['action'], at=command['at'])
            cursor += 1
        target = min(sim.session.time + 100, record['until'])
        if cursor < len(ordered):
            target = min(target, ordered[cursor]['submitted_at'])
        if head_cp is None and sim.session.time < 700 <= target:
            target = 700
        sim.session.advance(target - sim.session.time)
        if target == 700 and head_cp is None:
            head_cp = helper.write_checkpoint(sim, run_dir / 'head.checkpoint.json')
            write_canonical(run_dir / 'head.replay_driver.checkpoint.json',
                            {'command_cursor': cursor, 'record_sha256': sha(replay_path),
                             'checkpoint': head_cp, 'source_guard': sources})
        state = sim.ctx.state()
        progress = {'tick': target, 'kills': state['kills'], 'leaks': state['leaks'],
                    'pending': state['pending_waves'], 'finished': state['finished'],
                    'event_count': len(sim.session._events._records), 'phase': 'head_replay'}
        write_canonical(run_dir / 'head.progress.json', progress)
        print(json.dumps(progress), flush=True)
    while cursor < len(ordered) and ordered[cursor]['submitted_at'] == sim.session.time:
        command = ordered[cursor]
        sim.submit(command['action'], at=command['at'])
        cursor += 1
    if cursor != len(ordered):
        raise ValueError('Replay did not submit all commands')
    observed = helper.observations(sim, run_dir / 'head.events.jsonl')
    result['replayed_journal'] = observed['export']
    result['replay_equal'] = {k: observed[k] for k in d['observations']} == d['observations']
    if d['public_dialogue_driver']:
        from tools.control_driver.public_ack_v2 import PublicAckDriver
        # Replayed submitted public acknowledgements and the final event cursor
        # reconstruct the external driver without inserting another command.
        driver = PublicAckDriver(sim, d['driver_final'])
        result['recovery']['head_driver_equal'] = driver.checkpoint() == d['driver_final']
    else:
        result['recovery']['head_driver_equal'] = True
    after = {path: sha(path) for path in sources}
    result['source_at_completion'] = {path: sha(path) for path in original_sources}
    result['core_at_completion'] = implementation_digest()
    result['recovery']['source_at_recovery_completion'] = after
    result['identity_stable'] = (after == sources and result['core_at_completion'] == d['implementation'])
    expected = Counter(d['expected_births'])
    actual = Counter(e['definition_id'] for e in sim.session.world.entities() if 'enemy' in e['tags'])
    result['recovery']['head_wave_conservation'] = actual == expected and state['kills'] + state['leaks'] == sum(expected.values())
    result['passed'] = all((result['process_complete'], result['checkpoint_equal'],
                            result['durable_checkpoint_equal'], result['replay_equal'],
                            result['driver_equal'], result['identity_stable'],
                            result['recovery']['head_driver_equal'],
                            result['recovery']['head_wave_conservation']))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    write_canonical(a.output, result)
    print(json.dumps({'passed': result['passed'], 'output': str(a.output)}), flush=True)
    del sim
    gc.collect()
    import subprocess
    import os
    folders = [run_dir]
    if a.prior.parent.resolve().is_relative_to(log_root):
        folders.append(a.prior.parent)
    for folder in folders:
        subprocess.run([sys.executable, str(ROOT / 'tools/cleanup_simulation_logs.py'),
                        '--run-dir', str(folder), '--apply', '--minimum-age-minutes', '0',
                        '--completed-pid', str(os.getpid())],
                       cwd=ROOT, check=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
