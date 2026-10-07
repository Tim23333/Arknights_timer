"""Package local frozen runtimes and pinned source bytes for Git-only handoff.

This is a handoff operation, not a simulation. Every restored file is bound to
its actual SHA256. Blob chunks stay below GitHub's ordinary file-size limit.
Historical missing/deleted paths are inventoried, never manufactured.
"""
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
OUT = ROOT / 'reference/portable_20261007'
SHA = re.compile(r'^[0-9a-f]{64}$')


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for part in iter(lambda: source.read(1024 * 1024), b''):
            value.update(part)
    return value.hexdigest()


def resolve(value):
    path = Path(value)
    if path.is_absolute():
        return path
    if value.replace('\\', '/').startswith(('unpack_work/', 'data/', 'ark_parser/', 'Ark_data/')):
        return REPO / path
    return ROOT / path


def main():
    if (OUT / 'manifest.json').exists():
        raise FileExistsError('Preserve completed handoff bundle')
    OUT.mkdir(parents=True, exist_ok=True)
    tracked = set(subprocess.check_output(['git', '-c', 'core.longpaths=true', 'ls-files'], cwd=REPO,
                                         text=True, encoding='utf8').splitlines())
    chosen, missing, drift = {}, {}, []
    scanned = 0

    def choose(value, pin=None, origin=None):
        if not value or '\x00' in value or value.startswith(('http:', 'https:', 'codex:', 'plugin:')):
            return
        try:
            path = resolve(value).resolve()
        except (OSError, ValueError):
            return
        # Raw simulation evidence is intentionally excluded by user policy.
        if 'arksimlogs' in str(path).lower() and 'receipts' not in str(path).lower():
            return
        if not path.is_file():
            if pin and ('unpack_work' in str(path) or 'arksimlogs' in str(path).lower()):
                missing[str(path)] = {'legacy_path': str(path), 'expected_sha256': pin, 'referenced_by': origin}
            return
        if path.is_relative_to(OUT) or '__pycache__' in path.parts:
            return
        if path.is_relative_to(REPO):
            relative = path.relative_to(REPO).as_posix()
            if relative in tracked:
                return
            # Uncommitted emulator work will be committed directly, not hidden
            # inside an archive. Only ignored native/runtime input is bundled.
            if relative.startswith('Ark_emulator/'):
                return
            destination = {'kind': 'repo', 'path': relative}
        else:
            destination = {'kind': 'external', 'path': 'external_sources/' + hashlib.sha256(str(path).encode()).hexdigest()[:20] + '/' + path.name}
        row = chosen.setdefault(str(path), {'source': path, 'destination': destination, 'pins': set(), 'origins': set()})
        if pin:
            row['pins'].add(pin)
        if origin:
            row['origins'].add(origin)

    def walk(value, origin):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and isinstance(item, str) and SHA.fullmatch(item):
                    choose(key, item, origin)
                if isinstance(item, (dict, list)):
                    walk(item, origin)
            if isinstance(value.get('path'), str):
                pin = value.get('sha256')
                choose(value['path'], pin if isinstance(pin, str) and SHA.fullmatch(pin) else None, origin)
        elif isinstance(value, list):
            for item in value:
                walk(item, origin)

    for folder in ('packages/campaign', 'validation/campaign'):
        for path in (ROOT / folder).rglob('*.json'):
            if path.stat().st_size > 8 * 1024 * 1024:
                continue
            try:
                value = json.loads(path.read_bytes())
            except (ValueError, OSError):
                continue
            scanned += 1
            walk(value, path.relative_to(ROOT).as_posix())
    runtimes = []
    for folder in sorted((REPO / 'unpack_work').iterdir()):
        runtime = folder / 'ark_sim'
        if not runtime.is_dir():
            continue
        files = []
        for path in runtime.rglob('*'):
            if path.is_file() and path.suffix in ('.py', '.json') and not set(path.parts) & {'__pycache__', 'validation'}:
                choose(str(path), origin='frozen-runtime-inventory')
                files.append(path.relative_to(folder).as_posix())
        runtimes.append({'name': folder.name, 'repo_path': folder.relative_to(REPO).as_posix(), 'source_files': len(files)})
    # The preflight explicitly consumes sealed archived forward/CP receipts.
    archive = Path('E:/ArkSimLogs/receipts/paused_20261005')
    if archive.exists():
        for path in archive.rglob('*.json'):
            if path.stat().st_size < 5 * 1024 * 1024:
                choose(str(path), origin='sealed-pre-pause-receipt')
    blobs, entries = {}, []
    for index, (legacy, row) in enumerate(sorted(chosen.items())):
        path = row['source']
        actual = sha(path)
        if row['pins'] and actual not in row['pins']:
            drift.append({'legacy_path': legacy, 'actual_sha256': actual, 'historical_expected': sorted(row['pins']), 'origins': sorted(row['origins'])})
        if actual not in blobs:
            compressed = gzip.compress(path.read_bytes(), compresslevel=6, mtime=0)
            chunks = []
            for part, offset in enumerate(range(0, len(compressed), 32 * 1024 * 1024)):
                chunk = compressed[offset:offset + 32 * 1024 * 1024]
                dest = OUT / 'blobs' / (actual + '.' + str(part) + '.gzpart')
                dest.parent.mkdir(exist_ok=True)
                dest.write_bytes(chunk)
                chunks.append({'path': dest.relative_to(OUT).as_posix(), 'bytes': len(chunk), 'sha256': hashlib.sha256(chunk).hexdigest()})
            blobs[actual] = {'raw_bytes': path.stat().st_size, 'compressed_bytes': len(compressed), 'chunks': chunks}
        entries.append({'legacy_path': legacy, 'destination': row['destination'], 'sha256': actual,
                        'historical_pins': sorted(row['pins']), 'referenced_by': sorted(row['origins'])})
        if index % 1000 == 0:
            print(json.dumps({'bundled_files': index, 'unique_blobs': len(blobs)}), flush=True)
    manifest = {'schema': 'ark-sim/git-only-source-bundle/v1', 'legacy_repo_root': str(REPO),
                'entries': entries, 'blobs': blobs, 'runtimes': runtimes,
                'source_json_scanned': scanned, 'missing_historical_references': list(missing.values()),
                'historical_pin_drift': drift, 'raw_simulation_logs_included': False,
                'external_source_path_policy': 'Restore externally rooted compact sources below repo/external_sources; use the manifest resolver. Never overwrite old receipt identities.',
                'raw_bytes_with_duplicates': sum(row['source'].stat().st_size for row in chosen.values()),
                'unique_raw_bytes': sum(row['raw_bytes'] for row in blobs.values()),
                'git_blob_bytes': sum(row['compressed_bytes'] for row in blobs.values())}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: manifest[key] for key in ('source_json_scanned', 'raw_bytes_with_duplicates', 'unique_raw_bytes', 'git_blob_bytes')} | {'files': len(entries), 'runtimes': len(runtimes), 'missing_historical_references': len(missing), 'historical_pin_drift': len(drift)}))


if __name__ == '__main__':
    main()
