"""Adapt completed suite evidence without rerunning or granting conversion approval."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(root, value):
    path = (root/str(value).replace('\\', '/')).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('evidence reference exits workspace')
    return path


def adapt(source_path, root=ROOT, current_implementation=None):
    root = Path(root).resolve(); source_path = Path(source_path).resolve()
    source = json.loads(source_path.read_bytes())
    if (source.get('schema') != 'ark-sim/test-execution-evidence/v1' or source.get('passed') is not True
            or type(source.get('exit_code')) is not int or source['exit_code'] != 0):
        raise ValueError('only a completed successful execution artifact can be exported')
    match = re.fullmatch(r'(\d+) passed in ([0-9.]+)s(?: \([0-9:]+\))?', source.get('summary', ''))
    if not match or int(match[1]) <= 0:
        raise ValueError('complete passing summary is required')
    log = inside(root, source['log'])
    if sha(log) != source['log_sha256'] or source['summary'] not in log.read_text(encoding='utf8'):
        raise ValueError('completed log identity or summary differs')
    implementation = source['implementation_digest_at_completion']
    if current_implementation is None:
        from ark_sim.adapters.api import implementation_digest
        current_implementation = implementation_digest()
    if implementation != current_implementation:
        raise ValueError('execution implementation differs from current source')
    records = source.get('test_sources_at_completion')
    if not isinstance(records, dict) or not records:
        raise ValueError('completed test-source identity map is required')
    tests, dependencies = [], []
    for value, expected in sorted(records.items()):
        path = inside(root, value)
        if not path.is_file() or sha(path) != expected:
            raise ValueError('test source is missing or changed: '+str(value))
        record = {'path': path.relative_to(root).as_posix(), 'source_sha256': expected,
            'result': 'passed', 'execution_scope': 'completed full selected suite'}
        (tests if path.name.startswith('test_') else dependencies).append(record)
    if not tests:
        raise ValueError('artifact contains no executed test modules')
    return {'schema': 'ark-sim/campaign-test-evidence/v1', 'passed': True,
        'implementation_sha256': implementation, 'tests': tests,
        'dependency_sources_verified': dependencies, 'execution_summary': source['summary'],
        'tests_passed': int(match[1]), 'elapsed_seconds': float(match[2]), 'command': source['command'],
        'source_execution_artifact': str(source_path.relative_to(root)), 'source_execution_sha256': sha(source_path),
        'log': log.relative_to(root).as_posix(), 'log_sha256': source['log_sha256'],
        'adapter_sha256': sha(Path(__file__)), 'export_reverified_sources': True,
        'new_tests_after_execution_are_not_included': True,
        'conversion_review_receipt': False, 'formal_stage_approved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = adapt(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'exported': str(args.output), 'tests_passed': result['tests_passed'],
        'test_modules': len(result['tests']), 'formal_stage_approved': False}))


if __name__ == '__main__':
    main()
