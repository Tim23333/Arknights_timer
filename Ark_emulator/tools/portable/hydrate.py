"""Verify/restore the committed reference bundle; never starts simulations."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
BUNDLE = ROOT / 'reference/portable_20261007'


def file_sha(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def target(repo, relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or any(':' in part for part in path.parts):
        raise ValueError('Unsafe bundle destination: ' + relative)
    value = repo.joinpath(*path.parts).resolve()
    if not value.is_relative_to(repo.resolve()):
        raise ValueError('Destination leaves intended repo')
    return value


def decode(bundle, row):
    payload = bytearray()
    for chunk in row['chunks']:
        path = target(bundle, chunk['path'])
        if path.stat().st_size != chunk['bytes'] or file_sha(path) != chunk['sha256']:
            raise ValueError('Compressed blob changed: ' + str(path))
        payload.extend(path.read_bytes())
    if len(payload) != row['compressed_bytes']:
        raise ValueError('Compressed byte count differs')
    return gzip.GzipFile(fileobj=io.BytesIO(payload))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-archive', action='store_true', help='Verify all unique raw blobs without restoring files')
    parser.add_argument('--restore', action='store_true', help='Restore missing exact-byte inputs into this clone')
    parser.add_argument('--destination-repo', type=Path, help='Explicit alternate root for handoff restore verification')
    parser.add_argument('--output', type=Path, help='Write a compact integrity receipt')
    args = parser.parse_args()
    destination_repo = (args.destination_repo or REPO).resolve()
    manifest = json.loads((BUNDLE / 'manifest.json').read_bytes())
    written = skipped = 0
    checked = set()
    if args.check_archive:
        for key, row in manifest['blobs'].items():
            value, size = hashlib.sha256(), 0
            with decode(BUNDLE, row) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    value.update(block)
                    size += len(block)
                    if size > row['raw_bytes']:
                        raise ValueError('Blob expands beyond its declared size')
            if value.hexdigest() != key or size != row['raw_bytes']:
                raise ValueError('Raw blob identity differs: ' + key)
            checked.add(key)
    if args.restore:
        for row in manifest['entries']:
            destination = target(destination_repo, row['destination']['path'])
            if destination.exists():
                if not destination.is_file() or file_sha(destination) != row['sha256']:
                    raise ValueError('Existing file differs; preserved without overwrite: ' + str(destination))
                skipped += 1
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            blob = manifest['blobs'][row['sha256']]
            value, size = hashlib.sha256(), 0
            temporary = destination.with_name(destination.name + '.hydrate.tmp')
            try:
                with decode(BUNDLE, blob) as source, temporary.open('xb') as sink:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        value.update(block)
                        size += len(block)
                        if size > blob['raw_bytes']:
                            raise ValueError('Blob expands beyond its declared size')
                        sink.write(block)
                if value.hexdigest() != row['sha256'] or size != blob['raw_bytes']:
                    raise ValueError('Restored identity differs: ' + str(destination))
                temporary.replace(destination)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            written += 1
        # Consumers can resolve legacy absolute source names without rewriting
        # the immutable original receipt or original content fingerprint.
        mapping = {row['legacy_path']: str(target(destination_repo, row['destination']['path'])) for row in manifest['entries']}
        state = destination_repo / 'unpack_work/portable_state'
        state.mkdir(parents=True, exist_ok=True)
        (state / 'legacy_paths.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    report = {'schema': 'ark-sim/portable-bundle-integrity/v1', 'passed': True,
              'manifest_sha256': file_sha(BUNDLE / 'manifest.json'), 'unique_blobs_checked': len(checked),
              'restored_files': written, 'identical_existing_files': skipped,
              'bundle_files': len(manifest['entries']), 'frozen_runtimes': len(manifest['runtimes']),
              'destination_repo': str(destination_repo),
              'historical_missing_paths': len(manifest['missing_historical_references']),
              'historical_path_drift': len(manifest['historical_pin_drift']),
              'simulations_started': False, 'historical_receipts_rewritten': False}
    if args.output:
        if args.output.exists():
            raise FileExistsError('Preserve previous integrity receipt')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
