"""Compare every source value; permit only the actual runtime identity change."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path('E:/ArkSimEvidence/projectile_leaf_v1')
OUT = ROOT / 'validation/campaign/chapter08_projectile_leaf_v1/source400_comparison.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = [FOLDER / 'parent400.json', FOLDER / 'candidate400.json']
    parent, candidate = [json.loads(path.read_bytes()) for path in paths]
    original_runtime = parent['checkpoint']['runtime_fingerprint']
    candidate_runtime = candidate['checkpoint']['runtime_fingerprint']
    changes, rejected = [], []

    def compare(left, right, path=''):
        if type(left) is not type(right):
            rejected.append(path)
            return
        if isinstance(left, dict):
            if left.keys() != right.keys():
                rejected.append(path)
                return
            for key in left:
                compare(left[key], right[key], path + '/' + key)
        elif isinstance(left, list):
            if len(left) != len(right):
                rejected.append(path)
                return
            for index, (a, b) in enumerate(zip(left, right)):
                compare(a, b, path + '/' + str(index))
        elif left != right:
            if path == '/core' or path.endswith('/runtime_fingerprint') and left == original_runtime and right == candidate_runtime:
                changes.append(path)
            else:
                rejected.append(path)

    compare(parent, candidate)
    assert not rejected, rejected[:20]
    timings = [json.loads(path.with_suffix('.timing.json').read_bytes()) for path in paths]
    result = {'passed': True, 'parent_core': parent['core'], 'candidate_core': candidate['core'],
              'all_values_compared': True, 'allowed_exact_identity_differences': changes,
              'rejected_differences': rejected, 'source_input_scope': 'Native7row firstscreen actual through400 tick, no delayed clock changes',
              'capture_pins': {str(path): sha(path) for path in paths},
              'timings': timings, 'speed_ratio': timings[0]['simulation_seconds'] / timings[1]['simulation_seconds'],
              'speed_limit': 'Single paired process capture; not a statistical throughput guarantee',
              'whole_stage_approved': False}
    assert not OUT.exists()
    OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'sha': sha(OUT), 'identity_differences': changes,
                      'speed_ratio': result['speed_ratio']}))


if __name__ == '__main__':
    main()
