"""Promote exact validated V2 bytes; preserve old production for recovery."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OLD = '94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'
NEW = '08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
ADMISSION_SHA = 'c0d85fe8725fefd2f38aa6851070bcbe98a2d59d1fbecbe42254776e54a5dc6c'
FREEZE_SHA = 'dffd04f781fe2f79ffae043c2c572e77520c26bf8c101fdd4057ef83b7bdc567'
OUT = ROOT / 'validation/campaign/chapter10_primary08_v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*')
            if p.is_file() and p.suffix in ('.py', '.json') and 'validation' not in p.relative_to(root).parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    from ark_sim.adapters.api import implementation_digest
    if implementation_digest() != OLD:
        raise ValueError('Production changed since approved parent')
    gate_path = ROOT / 'validation/campaign/campaign_resource_channel_full_v1/completed.gates.v2.json'
    freeze_path = ROOT / 'validation/campaign/campaign_resource_channel_v1/freeze.functional.v1.json'
    if sha(gate_path) != ADMISSION_SHA or sha(freeze_path) != FREEZE_SHA:
        raise ValueError('Completed proof identity differs')
    gate, freeze = json.loads(gate_path.read_bytes()), json.loads(freeze_path.read_bytes())
    if not gate['source_reference_kernel_gates_complete'] or gate['core'] != NEW or not all(gate['checks'].values()):
        raise ValueError('Completed kernel and input gates required')
    for proof in [*gate['proofs'].values(), gate['independent_actual_report']]:
        if sha(proof['path']) != proof['sha256']:
            raise ValueError('Consumed completed proof changed')
    candidate = args.candidate.resolve() / 'ark_sim'
    primary = ROOT / 'ark_sim'
    before, expected = inventory(primary), inventory(candidate)
    if {'ark_sim/' + k: v for k, v in expected.items()} != freeze['source_inventory']:
        raise ValueError('Candidate inventory differs from exact frozen runtime')
    if set(before) - set(expected):
        raise ValueError('Promotion must not discard production source files')
    changes = {name: {'before': before.get(name), 'after': value}
               for name, value in expected.items() if before.get(name) != value}
    record = {'schema': 'ark-sim/primary-promotion/v1', 'parent_core': OLD, 'core': NEW,
              'candidate': str(candidate), 'admission_sha256': ADMISSION_SHA, 'freeze_sha256': FREEZE_SHA,
              'before_inventory': before, 'expected_inventory': expected, 'changes': changes,
              'applied': False, 'whole_stage_completed': False, 'client_verified': False,
              'scope': 'Exact validated general V2 runtime; stage completion remains separately gated'}
    if not args.apply:
        print(json.dumps({'parent_core': OLD, 'core': NEW, 'changed_files': len(changes),
                          'new_files': sorted(set(expected) - set(before)), 'apply': False}))
        return 0
    receipt = OUT / 'promotion.v1.json'
    backup = OUT / 'parent_source'
    if receipt.exists() or backup.exists():
        raise FileExistsError('Preserve prior promotion and backup')
    OUT.mkdir(parents=True, exist_ok=True)
    for name in before:
        dest = backup / name;dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(primary / name, dest)
    if inventory(backup) != before:
        raise ValueError('Backup source did not preserve exact bytes')
    for name in changes:
        dest = primary / name;dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate / name, dest)
    after = inventory(primary)
    record.update(applied=True, after_inventory=after, bytes_equal=after == expected,
                  actual_core_after_copy=implementation_digest(), parent_backup=str(backup))
    receipt.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    if after != expected or implementation_digest() != NEW:
        raise ValueError('Promotion bytes or digest mismatch; inspect saved backup')
    print(json.dumps({'applied': True, 'core': NEW, 'changed_files': len(changes),
                      'all99_source_files_byte_equal': len(after) == 99 and after == expected}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
