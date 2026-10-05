"""Exact-context three-way integration, never wholesale receiver replacement."""
from pathlib import Path
import hashlib, json, shutil, difflib

ROOT = Path(__file__).resolve().parents[2]
U = (ROOT/'../unpack_work').resolve()
LEFT = U/'campaign_c9_mandra_v1_candidate'
BASE = U/'campaign_c9_rock_modes_v2_candidate'
RIGHT = U/'campaign_c9_receiver_hooks_v2_candidate'
DEST = U/'campaign_c9_finale_joint_v1_candidate'
HERE = Path(__file__).resolve().parent
OUT = ROOT/'validation/campaign/chapter09_finale_joint_v1'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
if not DEST.exists(): shutil.copytree(LEFT, DEST, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
freeze = json.loads((ROOT/'validation/campaign/chapter09_receiver_hooks_v2/freeze.v2.json').read_bytes())
receipt = {'schema': 'ark-sim/mechanical-three-way-merge/v1', 'base': str(BASE), 'left': str(LEFT),
           'right': str(RIGHT), 'destination': str(DEST), 'incoming_core': freeze['core'], 'files': []}
for row in freeze['delta']:
    rel = Path(row['path']); b = BASE/rel; l = LEFT/rel; incoming = RIGHT/rel; dest = DEST/rel
    assert sha(b) == row['before'] and sha(incoming) == row['after']
    assert dest.read_bytes() == l.read_bytes(), 'New candidate must still contain untouched left file'
    base_lines = b.read_text(encoding='utf8').splitlines(keepends=True)
    incoming_lines = incoming.read_text(encoding='utf8').splitlines(keepends=True)
    ours = l.read_text(encoding='utf8'); changes = []
    matcher = difflib.SequenceMatcher(None, base_lines, incoming_lines, autojunk=False)
    # Apply each complete unified-diff context group once; adjacent edits share
    # a group, so neither destroys the other's original anchor.
    for group in matcher.get_grouped_opcodes(3):
        i, j = group[0][1], group[-1][2]
        a, z = group[0][3], group[-1][4]
        old = ''.join(base_lines[i:j]); new = ''.join(incoming_lines[a:z])
        assert ours.count(old) == 1, (rel, i, j, ours.count(old))
        ours = ours.replace(old, new, 1)
        changes.append({'base_lines': [i+1, j], 'incoming_lines': [a+1, z],
                        'opcodes': [list(row) for row in group], 'context_match_count': 1})
    dest.write_text(ours, encoding='utf8')
    for label, path in [('base', b), ('left', l), ('right', incoming), ('merged', dest)]:
        saved = HERE/'merge_inputs'/label/rel; saved.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, saved)
    patches = {}
    for label, path, end in [('incoming_vs_base', b, incoming), ('merged_vs_left', l, dest)]:
        diff = ''.join(difflib.unified_diff(path.read_text(encoding='utf8').splitlines(keepends=True),
            end.read_text(encoding='utf8').splitlines(keepends=True), fromfile=str(path), tofile=str(end)))
        saved = HERE/'diffs'/(rel.name+'.'+label+'.diff'); saved.parent.mkdir(exist_ok=True); saved.write_text(diff, encoding='utf8')
        patches[label] = {'path': saved.relative_to(ROOT).as_posix(), 'sha256': sha(saved)}
    receipt['files'].append({'path': rel.as_posix(), 'base_sha256': sha(b), 'left_sha256': sha(l),
        'incoming_sha256': sha(incoming), 'merged_sha256': sha(dest), 'changes': changes, 'diffs': patches})
path = OUT/'merge.v1.json'; assert not path.exists(); path.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf8')
print(json.dumps({'candidate': str(DEST), 'merge_files': len(receipt['files'])}))
