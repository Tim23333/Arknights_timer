"""Resolve executed mechanism cases; evidence presence alone is not approval."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def workspace_file(root, relative):
    root = Path(root).resolve()
    path = (root/relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Mechanism evidence must be an existing workspace file')
    return path


def resolve_case(root, reference, implementation, package_sha256):
    """Return a frozen event witness for one named executed case.

    This validates identity and observations. It does not decide whether the
    independent expectation is correct or whether a stage is complete.
    """
    path = workspace_file(root, reference['path'])
    if sha(path) != reference['sha256']:
        raise ValueError('Mechanism evidence identity mismatch')
    record = json.loads(path.read_bytes())
    if record.get('passed') is not True or record.get('identity_stable') is not True:
        raise ValueError('Mechanism evidence did not finish successfully with stable identity')
    if record.get('implementation_sha256') != implementation:
        raise ValueError('Mechanism evidence belongs to a different implementation')
    actual_package = record.get('input_package_sha256',record.get('package_sha256'))
    if actual_package != package_sha256:
        raise ValueError('Mechanism evidence belongs to a different content package')
    tests = record.get('tests')
    if not tests:
        raise ValueError('Mechanism evidence lacks executed source references')
    for test in tests:
        source = workspace_file(root,test['path'])
        if test.get('result') != 'passed' or sha(source) != test.get('source_sha256'):
            raise ValueError('Mechanism test source or result is stale')
    name = reference['case']
    if name not in record.get('selected_cases',[]):
        raise ValueError('Mechanism case was not selected for this run')
    cases = record.get('cases',{})
    if isinstance(cases,dict):
        actual = cases.get(name)
    elif isinstance(cases,list):
        matches = [c for c in cases if c.get('case') == name]
        if len(matches) != 1 or matches[0].get('result') != 'passed':
            raise ValueError('Mechanism case result is absent, ambiguous or failed')
        actual = matches[0].get('actual')
    else:
        raise ValueError('Unsupported mechanism case collection')
    if not isinstance(actual,dict):
        raise ValueError('Executed mechanism case is missing')
    if actual.get('checkpoint_equal') is not True or actual.get('replay_equal') is not True:
        raise ValueError('Mechanism case lacks checkpoint/replay equality')
    if not actual.get('events') or not actual.get('program_fingerprint') or not actual.get('runtime_fingerprint'):
        raise ValueError('Mechanism case lacks observed events or runtime identity')
    required_events = reference.get('required_event_types',[])
    observed = {e['type'] for e in actual['events']}
    if not required_events or not set(required_events) <= observed:
        raise ValueError('Required mechanism event types were not observed')
    return {'path':reference['path'],'sha256':reference['sha256'],'case':name,
        'program_fingerprint':actual['program_fingerprint'],'runtime_fingerprint':actual['runtime_fingerprint'],
        'observed_event_types':sorted(observed),'source_tests':tests,'formal_approval':False}


def resolve_requirements(root, requirements, implementation, package_sha256):
    if not requirements:
        raise ValueError('Required mechanism mapping is empty')
    resolved = {}
    for name, references in requirements.items():
        if not isinstance(name,str) or not name or not isinstance(references,list) or not references:
            raise ValueError('Each required mechanism needs named executed cases')
        resolved[name] = [resolve_case(root,r,implementation,package_sha256) for r in references]
    return resolved
