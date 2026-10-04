"""Reconstruct the frozen isolated joint runtime from its exact base and delta."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def inventory(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file() and path.suffix in ('.py', '.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_bytes())
    base = args.base_root.resolve()
    output = args.output.resolve()
    assert inventory(base / 'ark_sim') == manifest['base_inventory'], 'Base source identity differs'
    assert inventory(HERE / 'source_delta') == manifest['delta'], 'Stored delta differs'
    assert not output.exists(), 'Use a fresh isolated output directory'
    shutil.copytree(base / 'ark_sim', output / 'ark_sim',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in manifest['delta']:
        target = output / 'ark_sim' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / 'source_delta' / name, target)
    assert inventory(output / 'ark_sim') == manifest['candidate_inventory']
    core = subprocess.check_output([
        sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(output)], cwd=output, text=True).strip()
    assert core == manifest['candidate_core'], 'Reconstructed runtime digest differs'
    print(json.dumps({'core': core, 'output': str(output), 'candidate_only': True}))


if __name__ == '__main__':
    main()
