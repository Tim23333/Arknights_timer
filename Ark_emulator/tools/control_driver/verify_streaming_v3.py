"""Actual native story parity, disk restore/head and strict bounded-read proof."""
import copy
import gc
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ark_sim import Compiler, Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import digest, thaw
from ark_sim.tools.replay import replay
from tools.candidates.m77_event_storage.campaign_streaming_evidence_v14 import observations, write_checkpoint, load_checkpoint
from tools.control_driver.public_ack_v2 import PublicAckDriver as Old
from tools.control_driver.public_ack_v3 import PublicAckDriver as New
from tools.run_with_log_cleanup import save

CORE = '08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
LOG = Path(os.environ['ARKSIM_RUN_DIR'])
OUT = ROOT / 'validation/campaign/campaign_public_ack_streaming_v3/actual.v1.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(sim, path):
    value = observations(sim, path)
    return {key: value[key] for key in ('snapshot', 'events', 'event_count', 'continuation_state')}


class IndexedOnly:
    def __init__(self, actual):
        self.actual, self.reads = actual, 0

    def __len__(self):
        return len(self.actual)

    def __getitem__(self, index):
        if type(index) is not int:
            raise AssertionError('Driver requested an eager slice')
        self.reads += 1
        return self.actual[index]

    def __iter__(self):
        raise AssertionError('Driver iterated the complete record container')


def main():
    if OUT.exists():
        raise FileExistsError('Preserve original result')
    guards = {str(path): sha(path) for path in (ROOT / 'ark_sim').rglob('*')
              if path.is_file() and path.suffix in ('.py', '.json')}
    for name in ('public_ack_v2.py', 'public_ack_v3.py', 'verify_streaming_v3.py'):
        path = Path(__file__).with_name(name)
        guards[str(path)] = sha(path)
    cases = []
    for stage in ('level_main_00-10', 'level_main_00-11'):
        try:
            package_path = ROOT / 'packages/campaign/chapter0_stage_models' / (stage + '.source.v2.json')
            plan_path = package_path.with_name(stage + '.public.plan.v4.json')
            for path in (package_path, plan_path):
                guards[str(path)] = sha(path)
            package, plan = json.loads(package_path.read_bytes()), json.loads(plan_path.read_bytes())
            package['scenarioDraft']['commands'] = copy.deepcopy(plan['commands'])
            rejected = copy.deepcopy(next(row for row in plan['commands'] if row['action'] == 'deploy'))
            rejected.update(at=2, alias='blocked-input-probe')
            package['scenarioDraft']['commands'].insert(0, rejected)
            program = Compiler().compile(package)
            old = Engine.create(program, event_journal_path=LOG / (stage + '.old.active.jsonl'))
            old_driver = Old(old)
            old_driver.advance_to(180)
            sim = Engine.create(program, event_journal_path=LOG / (stage + '.new.active.jsonl'))
            driver = New(sim)
            driver.advance_to(4)
            cp = write_checkpoint(sim, LOG / (stage + '.checkpoint.json'))
            driver_cp = driver.checkpoint()
            disk_driver = LOG / (stage + '.driver.checkpoint.json')
            save(disk_driver, driver_cp)
            continued = Engine.restore(program, load_checkpoint(cp))
            continuation_driver = New(continued, json.loads(disk_driver.read_bytes()))
            assert thaw(sim.checkpoint()) == thaw(continued.checkpoint())
            driver.advance_to(180)
            continuation_driver.advance_to(180)
            head = replay(program, sim.export_replay(), event_journal_path=LOG / (stage + '.head.active.jsonl'))
            head_driver = New(head, driver.checkpoint())
            all_simulations = (old, sim, continued, head)
            values = [compact(item, LOG / (stage + '.' + str(index) + '.events.jsonl'))
                      for index, item in enumerate(all_simulations)]
            full = [thaw(item.checkpoint()) for item in all_simulations]
            assert all(item == values[0] for item in values)
            assert all(item == full[0] for item in full)
            drivers = [item.checkpoint() for item in (old_driver, driver, continuation_driver, head_driver)]
            assert all(item == drivers[0] for item in drivers)
            assert old.export_replay() == sim.export_replay() == continued.export_replay() == head.export_replay()
            # Real owned disk records prove the new driver never requests a
            # full-container list, tuple, slice or iterator during restoration.
            original = head.session._events._records
            spy = IndexedOnly(original)
            head.session._events._records = spy
            try:
                fresh = New(head, driver.checkpoint())
                fresh.observe()
                assert fresh.checkpoint() == driver.checkpoint()
                assert spy.reads == len(original)
                reads = spy.reads
            finally:
                head.session._events._records = original
            baseline = digest(thaw(head.checkpoint()))
            rejected_states = []
            for name in ('cursor', 'clock', 'program', 'runtime', 'event', 'step', 'submitted_at', 'at', 'missing_ack', 'duplicate_ack'):
                forged = copy.deepcopy(driver.checkpoint())
                if name == 'cursor': forged['cursor'] -= 1
                elif name == 'clock': forged['at'] -= 1
                elif name in ('program', 'runtime'): forged[name] = 'forged'
                elif name == 'missing_ack': forged['submitted'].pop()
                elif name == 'duplicate_ack': forged['submitted'].append(copy.deepcopy(forged['submitted'][0]))
                else: forged['submitted'][0][name] += 1
                try:
                    New(head, forged)
                except ValueError:
                    rejected_states.append(name)
                else:
                    raise AssertionError('Forged driver accepted: ' + name)
                assert digest(thaw(head.checkpoint())) == baseline
            completed = next(event for event in sim.session.events if event['type'] == 'control.completed'
                             and event['payload']['control'] == 'control/1')
            assert completed['time'] == (15 if stage.endswith('10') else 13)
            assert sim.ctx.resources.current('system/battle', 'life') == 99999
            cases.append({'stage': stage, 'passed': True, 'end': 180, 'four_full_observations': values,
                          'all4_domains_exact_V2_V3_CP_head': True, 'all_full_checkpoints_equal': True,
                          'full_checkpoint_digests': [digest(item) for item in full],
                          'full_driver_checkpoints_equal': True, 'public_replay_ledger_exact': True,
                          'driver_final': driver.checkpoint(), 'disk_driver_sha256': sha(disk_driver),
                          'strict_index_reads': reads, 'complete_owned_record_count': len(original),
                          'no_container_slice_or_iterator': True, 'forged_driver_states_rejected': rejected_states,
                          'failed_restores_leave_all_checkpoint_fields_unchanged': True,
                          'story_complete': completed['time'], 'native_UI_policy_verified': False})
            del old, sim, continued, head, full, all_simulations
        except Exception as error:
            cases.append({'stage': stage, 'passed': False, 'error': str(error), 'traceback': traceback.format_exc()})
        print(json.dumps({'stage': stage, 'passed': cases[-1]['passed']}), flush=True)
        gc.collect()
    report = {'schema': 'ark-sim/streaming-ACK-parity/v3', 'core': implementation_digest(),
              'cases': cases, 'source_at_start': guards,
              'source_at_completion': {path: sha(path) for path in guards},
              'policy': New.POLICY, 'whole_stage_verified': False}
    report['passed'] = all(row['passed'] for row in cases) and report['source_at_start'] == report['source_at_completion'] and report['core'] == CORE
    save(OUT, report)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
