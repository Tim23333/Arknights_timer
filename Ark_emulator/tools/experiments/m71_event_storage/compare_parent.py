"""Separate interpreter comparison; report only actual identity differences."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'validation/campaign/m71_event_storage'


def worker(runtime, output):
    sys.path.insert(0, runtime)
    from ark_sim import Compiler, Engine
    from ark_sim.contracts.models import thaw
    package = ROOT/'packages/ark_content/level_main_00_01.json'
    program = Compiler().compile(package)
    sim = Engine.create(program, seed=123)
    for item in json.loads((ROOT/'scenarios/level_main_00_01/commands.json').read_text(encoding='utf8')):
        action = dict(item)
        sim.submit(action, at=action.pop('at'))
    sim.session.advance(120)
    data = {'snapshot': sim.snapshot(), 'checkpoint': sim.checkpoint(), 'replay': sim.export_replay()}
    Path(output).write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding='utf8')


def differences(a, b, path=''):
    if type(a) is not type(b):
        return [{'path': path, 'expected': str(type(a)), 'actual': str(type(b))}]
    if isinstance(a, dict):
        result = []
        for key in sorted(set(a) | set(b)):
            pointer = path+'/'+key.replace('~', '~0').replace('/', '~1')
            if key not in a or key not in b:
                result.append({'path': pointer, 'reason': 'missing_key'})
            else:
                result.extend(differences(a[key], b[key], pointer))
        return result
    if isinstance(a, list):
        if len(a) != len(b):
            return [{'path': path, 'reason': 'length', 'expected': len(a), 'actual': len(b)}]
        return [diff for i, (left, right) in enumerate(zip(a, b))
                for diff in differences(left, right, path+'/'+str(i))]
    if isinstance(a, float):
        import struct
        equal = struct.pack('>d', a) == struct.pack('>d', b)
    else:
        equal = a == b
    return [] if equal else [{'path': path, 'expected': a, 'actual': b}]


def main():
    rows = []
    values = []
    for label, runtime in [('parent', ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'),
                           ('candidate', ROOT.parent/'unpack_work/campaign_m71_event_storage_candidate')]:
        output = OUT/(label+'-no-opt-full-values.json')
        subprocess.run([sys.executable, str(Path(__file__)), '--worker', str(runtime), str(output)], check=True)
        values.append(json.loads(output.read_text(encoding='utf8')))
        rows.append({'label': label, 'runtime': str(runtime), 'values': str(output),
                     'sha256': hashlib.sha256(output.read_bytes()).hexdigest()})
    actual = differences(*values)
    allowed = ['/checkpoint/runtime_fingerprint', '/replay/runtime_fingerprint', '/snapshot/runtime_fingerprint']
    assert sorted(diff['path'] for diff in actual) == allowed, actual
    report = {'passed': True, 'scope': '0-1 actual full values through tick 120, no storage opt-in',
              'runs': rows, 'differences': actual, 'all_other_values_and_types_equal': True,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'parent-no-opt-comparison.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
    else:
        main()
