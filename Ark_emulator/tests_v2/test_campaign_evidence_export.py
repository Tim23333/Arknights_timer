"""Evidence adaptation cannot launder a failure, stale source or new implementation."""
import hashlib
import json
import pytest

from tools.export_campaign_test_evidence import adapt


def fixture(root):
    tests = root/'tests_v2'; tests.mkdir()
    test = tests/'test_original.py'; test.write_text('def test_original():\n    assert True\n', encoding='utf8')
    log = root/'run.log'; log.write_text('1 passed in 0.01s\n', encoding='utf8')
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    data = {'schema': 'ark-sim/test-execution-evidence/v1', 'passed': True, 'exit_code': 0,
        'summary': '1 passed in 0.01s', 'command': 'python -m pytest tests_v2 -q',
        'implementation_digest_at_completion': 'known_runtime', 'log': 'run.log', 'log_sha256': sha(log),
        'test_sources_at_completion': {'tests_v2/test_original.py': sha(test)}}
    source = root/'execution.json'; source.write_text(json.dumps(data), encoding='utf8')
    return source, data, test, log


def test_export_retains_execution_identity_and_does_not_include_new_tests(tmp_path):
    source, data, test, log = fixture(tmp_path)
    (test.parent/'test_new.py').write_text('def test_new():\n    assert False\n', encoding='utf8')
    result = adapt(source, tmp_path, 'known_runtime')
    assert result['implementation_sha256'] == 'known_runtime'
    assert result['tests_passed'] == 1
    assert [t['path'] for t in result['tests']] == ['tests_v2/test_original.py']
    assert result['formal_stage_approved'] is False and result['conversion_review_receipt'] is False


@pytest.mark.parametrize('field,value', [('passed', False), ('exit_code', 1), ('exit_code', True), ('summary', '1 failed in 0.01s')])
def test_failure_or_partial_summary_cannot_become_passing_evidence(tmp_path, field, value):
    source, data, test, log = fixture(tmp_path)
    data[field] = value; source.write_text(json.dumps(data), encoding='utf8')
    with pytest.raises(ValueError):
        adapt(source, tmp_path, 'known_runtime')


@pytest.mark.parametrize('changed', ['source', 'log', 'implementation'])
def test_any_identity_change_rejects_instead_of_relabelling(tmp_path, changed):
    source, data, test, log = fixture(tmp_path)
    current = 'known_runtime'
    if changed == 'source':
        test.write_text('def test_original():\n    assert False\n', encoding='utf8')
    elif changed == 'log':
        log.write_text('1 failed in 0.01s\n', encoding='utf8')
    else:
        current = 'new_runtime'
    with pytest.raises(ValueError):
        adapt(source, tmp_path, current)
