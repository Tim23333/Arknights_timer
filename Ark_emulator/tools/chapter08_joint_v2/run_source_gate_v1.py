"""Collect actual source checks, durable checkpoints and execution identities."""
import contextlib
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v2_candidate'
CORE = 'a6ca7396556624768da2f83680ae34ad632d36dfa85f646916edbd1ee85f0128'
OUT = ROOT / 'validation/campaign/chapter08_joint_v2/source_gate_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(1, str(ROOT))
    import ark_sim
    import pytest
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter08_joint_v2 import test_burn_v1 as burn
    from tools.chapter08_joint_v2 import test_burn_reverse_v1 as reverse
    assert Path(ark_sim.__file__).resolve().is_relative_to(RUNTIME)
    assert implementation_digest() == CORE
    OUT.mkdir(exist_ok=False)
    selected = [Path(burn.__file__), Path(reverse.__file__)]
    files = set(selected + [Path(__file__)])
    for folder in (RUNTIME / 'ark_sim', ROOT / 'tools/chapter08_joint_v2',
                   ROOT / 'tools/chapter08_buff_lifetime', ROOT / 'tools/chapter08_boss'):
        files.update(path for path in folder.rglob('*') if path.is_file() and path.suffix in ('.py', '.json'))
    files.add(ROOT / 'tools/campaign_ordered_checkpoint.py')
    files.add(burn.MODULE)

    def guard():
        return {str(path): sha(path) for path in sorted(files)}

    before = guard()
    cases = []

    class Capture:
        def pytest_runtest_logreport(self, report):
            if report.when == 'call':
                cases.append({'nodeid': report.nodeid, 'outcome': report.outcome,
                              'seconds': report.duration,
                              'failure': str(report.longrepr) if report.failed else None})

        def pytest_runtest_teardown(self, item, nextitem):
            temporary = item.funcargs.get('tmp_path')
            if temporary:
                target = OUT / 'actual_ordered_checkpoints' / item.name
                target.mkdir(parents=True, exist_ok=True)
                for path in temporary.glob('*.json'):
                    shutil.copyfile(path, target / path.name)

    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = int(pytest.main([str(path) for path in selected] +
                              ['-q', '--import-mode=importlib'], plugins=[Capture()]))
    after = guard()
    report = {'core': implementation_digest(), 'actual_runtime_module': ark_sim.__file__,
              'cases': cases, 'exit_code': code, 'guards_start': before, 'guards_end': after,
              'guards_equal': before == after,
              'passed': code == 0 and before == after and len(cases) == 8,
              'scope': 'Author rerun of eight unchanged source expectations using actual D12 joint module; independent review is separate',
              'limits': 'Reference timing and Attr26 clamp are explicit policies; no complete Boss, whole stage or client proof',
              'formal_stage_approved': False, 'output': output.getvalue()}
    write(OUT / 'inputs.json', burn.INPUTS)
    write(OUT / 'captures.json', burn.CAPTURES)
    write(OUT / 'verification.json', report)
    write(OUT / 'artifact_pins.json', {str(path): sha(path) for path in OUT.rglob('*') if path.is_file()})
    print(json.dumps({'passed': report['passed'], 'cases': len(cases),
                      'report_sha': sha(OUT / 'verification.json')}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
