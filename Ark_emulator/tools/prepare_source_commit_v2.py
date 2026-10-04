"""Prepare an explicit source/input path list; never add running event logs."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / 'validation/campaign/source_commit_v2'
OUTPUT_DIR = re.compile(r'(evidence|independent|actual_ordered|captures|source_bound|required_|checkpoints|peer|_author|_boundaries|_clocks|ore_mine_joint|durable_|retained_|shield_occupancy_audit)')
OUTPUT_FILE = re.compile(r'(events|checkpoint|capture|observations|replay)')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    selected, excluded = set(), []
    for folder, extensions in [('ark_sim', {'.py', '.json'}), ('tests_v2', {'.py'}),
                               ('tools', {'.py', '.json', '.md', '.patch'}),
                               ('docs', {'.md', '.json', '.patch'}), ('scenarios', {'.json', '.md'})]:
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in extensions:
                assert path.stat().st_size < 25 * 1024 * 1024, str(path)
                selected.add(path)
    for path in (ROOT / 'packages').rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        relative = path.relative_to(ROOT / 'packages')
        output = any(OUTPUT_DIR.search(part) for part in relative.parts[:-1])
        output = output or bool(OUTPUT_FILE.search(path.name)) or path.suffix == '.jsonl'
        output = output or path.stat().st_size >= 25 * 1024 * 1024
        if output:
            excluded.append({'path': path.relative_to(REPO).as_posix(), 'bytes': path.stat().st_size,
                             'reason': 'Local execution evidence; preserved on disk, not source content'})
        elif path.suffix in {'.json', '.md', '.txt', '.asset', '.dat', '.ab', '.py'} or path.name == 'LICENSE':
            selected.add(path)
    for path in [REPO / '.gitattributes', ROOT / 'AGENTS.md', ROOT / 'README.md']:
        selected.add(path)
    # Freeze compact own-source gates and metadata only; full journals remain
    # on disk. These files identify the source and the retained proof locations.
    receipts = [
        'validation/campaign/campaign_foundation_v5/full_suite/verification.json',
        'validation/campaign/campaign_foundation_v5/baseline/verification.identity.json',
        'validation/campaign/campaign_foundation_v5/merge.json',
        'validation/campaign/campaign_foundation_v5_primary/promotion.json',
        'validation/campaign/chapter08_foundation_independent_final_v1/freeze.json',
        'validation/campaign/chapter08_foundation_independent_final_v1/verification.json',
        'validation/campaign/chapter08_foundation_pair_v1/verification.json',
        'validation/campaign/chapter08_visual_joint_independent_v1/freeze.json',
        'validation/campaign/chapter08_visual_joint_independent_v1/report.json',
        'validation/campaign/chapter08_visual_joint_terminal_independent_v1/report.json',
        'validation/campaign/campaign_foundation_v5/jt82_source_prefix_v1.json',
        'validation/campaign/campaign_foundation_v5/jt83_visual_source_prefix_v1.json',
        'validation/campaign/campaign_foundation_v5/chapter08_execution_plan_v1.json',
        'validation/trace_audit/chapter08_native_prefix_v2/verification.json',
        'validation/trace_audit/chapter08_arithmetic_author_v1.json',
        'validation/campaign/runthrough/registry.json',
    ]
    for relative in receipts:
        path = ROOT / relative
        assert path.is_file() and path.stat().st_size < 5 * 1024 * 1024, relative
        selected.add(path)
    # Include compact literal file references required by preserved tests and
    # source verification tools. Large execution journals remain local.
    for path in tuple(selected):
        if path.suffix != '.py':
            continue
        for relative in re.findall(r"['\"]((?:packages|scenarios|docs|validation)/[^'\"\r\n]+)['\"]", path.read_text(encoding='utf8', errors='replace')):
            referenced = ROOT / relative
            if referenced.is_file() and referenced.stat().st_size <= 2 * 1024 * 1024 and referenced.suffix != '.jsonl':
                selected.add(referenced)
    return sorted(selected), excluded


def main():
    selected, excluded = prepare()
    OUT.mkdir(parents=True, exist_ok=False)
    paths = [path.relative_to(REPO).as_posix() for path in selected]
    manifest = {'scope': 'V2 source, content inputs, authoring docs, compact evidence receipts; no unrelated Ark_data/backend/memory-tools or active event journals',
                'file_count': len(paths), 'bytes': sum(path.stat().st_size for path in selected),
                'files': {name: sha(path) for name, path in zip(paths, selected)},
                'preserved_local_evidence_not_added': excluded,
                'remaining_validation_outputs': 'Kept under Ark_emulator/validation and E:/ArkSimEvidence; only compact pinned receipts selected'}
    (OUT / 'manifest.json').write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    (OUT / 'paths.nul').write_bytes(b'\0'.join(name.encode('utf8') for name in paths) + b'\0')
    print(json.dumps({'files': len(paths), 'bytes': manifest['bytes'], 'excluded_package_evidence': len(excluded),
                      'manifest_sha': sha(OUT / 'manifest.json')}))


if __name__ == '__main__':
    main()
