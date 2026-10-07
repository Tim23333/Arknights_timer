"""Recover an already completed head after the V21 eager audit memory defect.

No Simulation is created. A read-only py-spy frame contains the complete four
observations returned by frozen R14 before V21 attempted its eager iteration.
The guard lease keeps the original files alive while that defective worker is
stopped. The actual export is independently read one record at a time; all
records, command outcomes, ACK ordering and source pins remain mandatory.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.cleanup_simulation_logs_v2 import pid_stamp
from tools.run_with_log_cleanup import save


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--stack', type=Path, required=True)
    parser.add_argument('--worker-pid', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if not run.is_relative_to(Path('E:/ArkSimLogs/runs').resolve()):
        raise ValueError('Existing fixed run required')
    if args.output.exists():
        raise FileExistsError('Preserve previous result')
    pf_path = ROOT / 'validation/campaign/chapter07_head_recovery_v21/preflight.v1.json'
    pf = json.loads(pf_path.read_bytes())
    if sha(pf_path) != '621db25bffc26190b8928384e00879641ce6402b32342b500f77666cbf4062d3':
        raise ValueError('Original admission identity differs')
    guards = pf['guards']
    for path, expected in guards.items():
        if sha(path) != expected:
            raise ValueError('Original source drift: ' + path)
    stack = json.loads(args.stack.read_text(encoding='utf-8-sig'))
    frames = [f for thread in stack if thread['pid'] == args.worker_pid
              for f in thread['frames'] if f['name'] == 'execute'
              and Path(f['filename']).resolve() == Path(__file__).with_name('recover_head.py')
              and f['line'] == 120]
    if len(frames) != 1:
        raise ValueError('Actual worker must be in the known eager audit call')
    local = {row['name']: row for row in frames[0]['locals']}
    observed = json.loads(local['observed']['repr'], object_pairs_hook=pairs)
    if set(observed) != {'snapshot', 'events', 'event_count', 'continuation_state'}:
        raise ValueError('Frame observations must be complete, never truncated')
    original_stamp = pid_stamp(args.worker_pid)
    if original_stamp is None:
        raise ValueError('Confirm actual live worker before acquiring guard')
    lease_path = run / 'run.lease.json'
    old_lease = json.loads(lease_path.read_bytes())
    workers = old_lease.get('workers', [{'pid': old_lease['worker_pid'], 'stamp': old_lease['worker_stamp']}])
    workers += [{'pid': args.worker_pid, 'stamp': original_stamp},
                {'pid': os.getpid(), 'stamp': pid_stamp(os.getpid())}]
    # The guard is a real audit worker of this same run, not a foreign PID.
    save(lease_path, {'completed': False, 'workers': workers,
                     'audit_guard': {'pid': os.getpid(), 'role': 'completed-head-streaming-audit'}})
    saved_stack = args.output.with_name('actual.readonly.worker.frame.v1.json')
    saved_stack.write_bytes(args.stack.read_bytes())
    result = {'schema': 'ark-sim/completed-head-streaming-audit/v22', 'passed': False,
              'new_simulation_created': False, 'original_eager_audit_defect': True,
              'original_worker_pid': args.worker_pid, 'original_worker_stamp': original_stamp,
              'guard_pid': os.getpid(), 'guard_stamp': pid_stamp(os.getpid()),
              'frame_path': str(saved_stack), 'frame_sha256': sha(saved_stack),
              'observations_origin': 'Read-only py-spy frame after frozen R14 returned; no target code execution',
              'new_head_observations': observed, 'source_at_start': guards,
              'historical_forward_CP_proof_reused': True,
              'historical_raw_deleted_cannot_be_fresh_read': True}
    save(args.output.with_name('audit.guard.ready.v1.json'), result)
    print(json.dumps({'guard_ready': True, 'guard_pid': os.getpid()}), flush=True)
    while pid_stamp(args.worker_pid) == original_stamp:
        time.sleep(1)
    try:
        spec = importlib.util.spec_from_file_location('archived_head_v21', Path(__file__).with_name('recover_head.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        historical, program, providers, helper, record, authenticated = module.authenticate()
        from ark_sim.adapters.api import implementation_digest
        from tools.control_driver.public_ack_v2 import PublicAckDriver
        if observed != historical['observations']:
            raise ValueError('All four complete head observations differ')
        export = run / 'head.events.jsonl'
        file_stat = export.stat()
        raw = hashlib.sha256()
        canonical = hashlib.sha256(b'[')
        waiting, responses = [], []
        count = 0
        previous_time = 0
        with export.open('rb') as source:
            for line in source:
                if not line.endswith(b'\n'):
                    raise ValueError('Incomplete event line')
                event = json.loads(line, object_pairs_hook=pairs)
                if not {'id', 'type', 'time', 'payload', 'cause'} <= set(event):
                    raise ValueError('Event fields missing')
                if type(event['id']) is not int or event['id'] != count + 1:
                    raise ValueError('Event ID is not contiguous')
                if type(event['time']) is not int or event['time'] < previous_time:
                    raise ValueError('Event time invalid')
                cause = event['cause']
                if cause is not None and (type(cause) is not int or not 0 < cause < event['id']):
                    raise ValueError('Event cause invalid')
                raw.update(line)
                if count:
                    canonical.update(b',')
                canonical.update(json.dumps(event, ensure_ascii=False, sort_keys=True,
                                             separators=(',', ':'), allow_nan=False).encode('utf8'))
                if event['type'] == 'control.awaiting_ack':
                    waiting.append(event)
                if event['type'] in ('command.accepted', 'command.rejected'):
                    responses.append(event)
                previous_time = event['time']
                count += 1
                if count % 500000 == 0:
                    print(json.dumps({'audit_records': count}), flush=True)
        canonical.update(b']')
        if count != observed['event_count'] or canonical.hexdigest() != observed['events']:
            raise ValueError('Actual full exported event values differ from completed head frame')
        if raw.hexdigest() != historical['journal']['sha256']:
            raise ValueError('Actual head bytes differ from original forward journal receipt')
        if export.stat() != file_stat or sha(export) != raw.hexdigest():
            raise ValueError('Export changed during independent audit')
        ordered = sorted(record['commands'], key=lambda row: row['order'])
        submitted = []
        for event in waiting:
            action = {'action': 'control_ack', 'control': event['payload']['control'], 'step': event['payload']['step']}
            matches = [row for row in ordered if row['action'] == action]
            if len(matches) != 1:
                raise ValueError('Awaiting ACK has absent or ambiguous action')
            row = matches[0]
            if row['submitted_at'] < event['time'] or row['at'] != row['submitted_at'] + 1:
                raise ValueError('ACK clock or submission order differs')
            submitted.append({'event': event['id'], 'control': action['control'],
                              'step': action['step'], 'submitted_at': row['submitted_at'], 'at': row['at']})
        driver = {'policy': PublicAckDriver.POLICY, 'program': program.fingerprint,
                  'runtime': record['runtime_fingerprint'], 'at': record['until'],
                  'cursor': count, 'submitted': submitted}
        after = {path: sha(path) for path in guards}
        result.update(all4_observations_equal=True,
                      full_driver_equal=driver == historical['driver_final'], actual_driver=driver,
                      public_command_outcomes_equal=responses == historical['commands'],
                      identity_stable=after == guards and implementation_digest() == module.CORE,
                      source_at_completion=after, actual_core=implementation_digest(),
                      actual_head_export={'path': str(export), 'sha256': raw.hexdigest(),
                                          'bytes': file_stat.st_size, 'count': count},
                      head_terminated=True, head_state=historical['state'],
                      head_state_origin='Historical complete state, equality implied by exact full snapshot digest; not reread from stopped process',
                      head_wave_conservation=historical['actual_births'] == historical['expected_births']
                      and historical['state']['kills'] + historical['state']['leaks'] == sum(historical['expected_births'].values()),
                      head_wave_conservation_origin='Inherited original state under equal complete snapshot, not a new per-entity read')
        result['passed'] = all(result[key] is True for key in
                               ('all4_observations_equal', 'full_driver_equal',
                                'public_command_outcomes_equal', 'identity_stable', 'head_wave_conservation'))
    except Exception as error:
        result.update(error=str(error), traceback=traceback.format_exc())
    save(args.output, result)
    # Root performs the standard cleanup once both the old wrapper and this
    # guard have exited. No files disappear before the complete report exists.
    print(json.dumps({'passed': result['passed'], 'output': str(args.output)}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
