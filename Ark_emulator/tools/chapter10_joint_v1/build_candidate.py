"""Three-way source merge of two frozen candidates; production stays unchanged."""
import hashlib
import json
import difflib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'ark_sim'
BLOOD = ROOT.parent / 'unpack_work/campaign_c10_bloodline_v1_candidate/ark_sim'
CHAIN = ROOT.parent / 'unpack_work/campaign_c10_chain_v1_candidate/ark_sim'
OUTPUT = ROOT.parent / 'unpack_work/campaign_c10_joint_v1_candidate'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root):
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.json') and
            '__pycache__' not in p.parts and 'validation' not in p.parts}


def apply_unique_changes(base, incoming, current):
    original = base.splitlines(True)
    revised = incoming.splitlines(True)
    for tag, first, last, begin, end in difflib.SequenceMatcher(None, original, revised, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        old = ''.join(original[first:last])
        new = ''.join(revised[begin:end])
        if old:
            if current.count(old) != 1:
                raise ValueError('Three-way replacement has conflicting or ambiguous source context')
            current = current.replace(old, new, 1)
        else:
            anchor = original[first] if first < len(original) else original[-1]
            if current.count(anchor) != 1:
                raise ValueError('Three-way insertion has ambiguous source boundary')
            current = current.replace(anchor, new + anchor if first < len(original) else anchor + new, 1)
    return current


def main():
    blood_freeze = ROOT / 'validation/campaign/chapter10_bloodline_v1/final.freeze.v1.json'
    chain_freeze = ROOT / 'validation/campaign/chapter10_chain_v1/frozen.v1.json'
    blood = json.loads(blood_freeze.read_bytes())
    chain = json.loads(chain_freeze.read_bytes())
    for name, expected in blood['source_inventory'].items():
        p = BLOOD.parent / name
        if sha(p) != expected:
            raise ValueError('Frozen blood source drift: ' + name)
    for entry in chain['changed_sources']:
        p = Path(entry['candidate'])
        if not p.resolve().is_relative_to(CHAIN.resolve()) or sha(p) != entry['sha256']:
            raise ValueError('Frozen chain delta drift: ' + str(p))
        parent = Path(entry['parent'])
        if parent.exists() and sha(parent) != entry['parent_sha256']:
            raise ValueError('Frozen chain parent drift: ' + str(parent))
    base, left, right = sources(BASE), sources(BLOOD), sources(CHAIN)
    if OUTPUT.exists():
        raise FileExistsError('Preserve existing joint candidate')
    output = OUTPUT / 'ark_sim'
    output.mkdir(parents=True)
    differences, inventories = [], {}
    for name in sorted(set(base) | set(left) | set(right)):
        parent = base[name].read_bytes() if name in base else None
        a = left[name].read_bytes() if name in left else parent
        b = right[name].read_bytes() if name in right else parent
        if a == parent:
            merged, origin = b, 'chain' if b != parent else 'unchanged'
        elif b == parent or a == b:
            merged, origin = a, 'blood'
        else:
            if parent is None:
                raise ValueError('Conflicting added file: ' + name)
            merged = apply_unique_changes(parent.decode('utf8'), b.decode('utf8'), a.decode('utf8')).encode('utf8')
            origin = 'three_way_blood_plus_chain'
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(merged)
        inventories[name] = sha(target)
        if merged != parent:
            differences.append({'file': name, 'origin': origin,
                'base': sha(base[name]) if name in base else None,
                'blood': sha(left[name]) if name in left else None,
                'chain': sha(right[name]) if name in right else None, 'merged': sha(target)})
    # Runtime identity uses host-native str(relative_path); inventory remains
    # portable POSIX notation. Preserve the exact implementation_digest input.
    py = {str(Path(name)): value for name, value in inventories.items() if name.endswith('.py')}
    core = hashlib.sha256(json.dumps(py, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    record = {'schema': 'ark-sim/chapter10-joint-candidate/v1', 'utc': datetime.now(timezone.utc).isoformat(),
        'core': core, 'candidate': str(OUTPUT), 'parent': 'cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18',
        'blood': blood['core'], 'chain': chain['implementation'],
        'source_freezes': {str(p): sha(p) for p in (blood_freeze, chain_freeze, Path(__file__))},
        'inventory': inventories, 'differences': differences,
        'verification_status': 'New joint core: focused/full/baseline/independent gates pending',
        'production_changed': False, 'client_verified': False}
    dest = ROOT / 'validation/campaign/chapter10_joint_v1/merge.v1.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(record, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'core': core, 'changes': len(differences), 'source_files': len(inventories)}))


if __name__ == '__main__':
    main()
