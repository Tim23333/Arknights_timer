"""Mechanical merge of frozen cache atomicity and linked packet clocks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def core(path):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(path.resolve())], cwd=ROOT, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-core', required=True)
    args = parser.parse_args()
    parent = ROOT.parent / 'unpack_work/campaign_c9_foundation_v4_candidate'
    cache = ROOT.parent / 'unpack_work/campaign_c9_foundation_v5_candidate'
    linked = ROOT.parent / 'unpack_work/campaign_c9_linked_elemental_v2_candidate'
    output = ROOT.parent / 'unpack_work/campaign_c9_foundation_v6_candidate'
    assert core(parent) == '6e43f8827415f99f83b79ff676fae533afcfda56f326d93bef8cda488172d1f9'
    assert core(cache) == args.cache_core
    assert core(linked) == '5ba742c2868c45eb37a14c720001a307e77e30434da6743ee5e4c98a483c8736'
    assert not output.exists()
    changes = ['domains/attachments.py', 'content/schemas.py']
    for rel in changes:
        assert sha(cache / 'ark_sim' / rel) == sha(parent / 'ark_sim' / rel)
    shutil.copytree(cache, output, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for rel in changes:
        shutil.copyfile(linked / 'ark_sim' / rel, output / 'ark_sim' / rel)
    manifest = {'core': core(output), 'cache_parent': args.cache_core,
        'linked_parent': core(linked), 'copied_linked_files': changes,
        'files': {p.relative_to(output).as_posix(): sha(p)
                  for p in (output / 'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py', '.json'}},
        'scope': 'Mechanical independent changes; all runtime gates must execute on this new identity',
        'own_full_pending': True, 'own_baseline_pending': True,
        'independent_peer_pending': True, 'promoted': False}
    folder = ROOT / 'validation/campaign/chapter09_foundation_v6'
    folder.mkdir(exist_ok=False)
    (folder / 'merge.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'core': manifest['core'], 'promoted': False}))


if __name__ == '__main__':
    main()
