"""Runthrough progress must preserve identity and keep accuracy pending."""
import copy
import json

from tools.build_campaign_runthrough_input import apply, encoded
from tools.campaign_runthrough_progress import inspect, sha
from tools.experiments.runthrough.test_profile import fixture


def files(tmp_path):
    parent = tmp_path/'parent.json'; parent.write_bytes(encoded(fixture()))
    package = tmp_path/'package.json'; package.write_bytes(encoded(apply(fixture(), sha(parent))))
    commands = tmp_path/'commands.json'; commands.write_text('[]\n', encoding='utf8')
    p = json.loads(package.read_bytes())
    report = {'schema': 'ark-sim/campaign-runthrough/v1', 'implementation': 'core/test',
              'package_sha256': sha(package), 'commands_sha256': sha(commands),
              'source_at_start': {'source': 'same'}, 'source_at_completion': {'source': 'same'},
              'identity_stable': True, 'profile': p['scenarioDraft']['metadata']['runthrough_profile'],
              'expected_births': {'unit/enemy': 3}, 'actual_births': {'unit/enemy': 3},
              'state': {'finished': True, 'pending_waves': 0, 'timeline': {'phase': 'complete'}, 'kills': 0, 'leaks': 3},
              'process_complete': True, 'passed': True, 'commands': [], 'checkpoint_equal': True, 'replay_equal': True,
              'end_tick': 20, 'base_life_final': 99996, 'actual_game_accuracy_verified': False}
    entry = {'report': 'report.json', 'package': 'package.json', 'parent_package': 'parent.json',
             'commands': 'commands.json', 'implementation': 'core/test'}
    save(tmp_path, report)
    return entry, report


def save(root, report):
    (root/'report.json').write_text(json.dumps(report), encoding='utf8')


def test_three_leaks_count_as_complete_and_deterministic_but_not_accurate(tmp_path):
    entry, _ = files(tmp_path); row = inspect(tmp_path, entry)
    assert row['process_status'] == 'complete'
    assert row['determinism_status'] == 'verified'
    assert row['accuracy_status'] == 'pending'
    assert row['leaks'] == 3


def test_self_claimed_accuracy_never_approves_client_data(tmp_path):
    entry, report = files(tmp_path); report['actual_game_accuracy_verified'] = True; save(tmp_path, report)
    row = inspect(tmp_path, entry)
    assert row['process_status'] == 'complete' and row['accuracy_status'] == 'pending'
    assert 'independent comparator receipt' in row['accuracy_reason']


def test_missing_replay_keeps_determinism_pending(tmp_path):
    entry, report = files(tmp_path); report.update(checkpoint_equal=None, replay_equal=None); save(tmp_path, report)
    row = inspect(tmp_path, entry)
    assert row['process_status'] == 'complete' and row['determinism_status'] == 'pending'


def test_changed_commands_are_stale(tmp_path):
    entry, _ = files(tmp_path); (tmp_path/'commands.json').write_text('[{}]\n', encoding='utf8')
    assert inspect(tmp_path, entry)['process_status'] == 'stale_or_invalid'


def test_unit_hp_cannot_be_changed_under_life_override(tmp_path):
    entry, report = files(tmp_path); path = tmp_path/'package.json'; p = json.loads(path.read_bytes())
    p['entities'][0]['components']['resources']['hp']['initial'] = 99999; path.write_bytes(encoded(p))
    report['package_sha256'] = sha(path); save(tmp_path, report)
    row = inspect(tmp_path, entry)
    assert row['process_status'] == 'stale_or_invalid' and 'beyond base life' in row['reason']


def test_population_missing_command_and_source_drift_are_rejected(tmp_path):
    entry, original = files(tmp_path)
    for mutate in (
        lambda r: r.update(expected_births={'unit/enemy': 4}),
        lambda r: r.update(commands=[{'type': 'command.accepted'}]),
        lambda r: r.update(source_at_completion={'source': 'changed'}),
    ):
        report = copy.deepcopy(original); mutate(report); save(tmp_path, report)
        assert inspect(tmp_path, entry)['process_status'] == 'stale_or_invalid'


def test_running_report_not_counted(tmp_path):
    entry, _ = files(tmp_path); (tmp_path/'report.json').unlink()
    assert inspect(tmp_path, entry)['process_status'] == 'running_or_not_reported'


def test_bounded_prefix_with_future_commands_is_incomplete_not_stale(tmp_path):
    entry, report = files(tmp_path); path=tmp_path/'commands.json'
    path.write_text('[{"at":100,"action":"skill"}]\n',encoding='utf8')
    report.update(commands_sha256=sha(path),process_complete=False,passed=False)
    report['state'].update(finished=False,pending_waves=1);save(tmp_path,report)
    assert inspect(tmp_path,entry)['process_status']=='incomplete'


def test_same_command_count_different_action_or_time_is_stale(tmp_path):
    entry,report=files(tmp_path);path=tmp_path/'commands.json';path.write_text('[{"at":1,"action":"skill","source":"actual"}]\n',encoding='utf8')
    report['commands_sha256']=sha(path);report['commands']=[{'time':1,'type':'command.accepted','payload':{'action':{'action':'skill','source':'wrong'}}}]
    save(tmp_path,report);assert inspect(tmp_path,entry)['process_status']=='stale_or_invalid'
    report['commands'][0].update(time=2);report['commands'][0]['payload']['action']['source']='actual'
    save(tmp_path,report);assert inspect(tmp_path,entry)['process_status']=='stale_or_invalid'


def test_missing_full_streaming_journal_is_stale(tmp_path):
    entry,report=files(tmp_path);report['observations']={'event_count':1};report['journal']={'path':'missing.events.jsonl','sha256':'wrong','events':1}
    save(tmp_path,report);assert inspect(tmp_path,entry)['process_status']=='stale_or_invalid'


def test_durable_checkpoint_claim_requires_saved_exact_bytes(tmp_path):
    entry,report=files(tmp_path);report.update(durable_checkpoint_equal=True,checkpoint='missing.cp.json',checkpoint_sha256='wrong',
        checkpoint_encoding='insertion-order JSON; loaded from actual saved bytes')
    save(tmp_path,report);assert inspect(tmp_path,entry)['process_status']=='stale_or_invalid'
    cp=tmp_path/'valid.cp.json';cp.write_text('{"z":1,"a":2}\n',encoding='utf8')
    report.update(checkpoint='valid.cp.json',checkpoint_sha256=sha(cp));save(tmp_path,report)
    assert inspect(tmp_path,entry)['durable_checkpoint_status']=='verified'
