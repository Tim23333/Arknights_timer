"""Launch one independently reviewed input; preserves all old run artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'validation/campaign/chapter02_03_refjoin_v1'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['02-10','03-08'], required=True)
    args = parser.parse_args()
    review = OUT / 'root_independent_source_review.json'
    assert sha(review) == '9585a59e0f52d86a03bd36d22c389c1cb5d8a581ed686b835deabcb79f41dc6f'
    proof = json.loads(review.read_bytes())
    assert proof['passed'] and all(row['passed'] for row in proof['results'])
    frozen = OUT / 'freeze.json'
    assert sha(frozen) == '41b6516c3f44ff3999c084614de928ad11f24d25a55d6036c36f187148f6c653'
    plan = json.loads(frozen.read_bytes())
    for rel, pin in plan['future_runner_support'].items():
        assert sha(ROOT / rel) == pin, rel
    selected = next(x for x in plan['planned_root_argv'] if x['stage'] == args.stage)
    argv = selected['argv']
    package = Path(argv[argv.index('--package')+1])
    commands = Path(argv[argv.index('--commands')+1])
    assert sha(package) == selected['package_sha'] and sha(commands) == selected['commands_sha']
    target = Path(selected['proposed_output'])
    assert not target.exists() and not target.with_suffix('.active.jsonl').exists()
    start = OUT / (args.stage + '.root_launch.json')
    with start.open('x', encoding='utf8') as f:
        json.dump({'stage':args.stage, 'argv':argv, 'source_review_sha':sha(review),
                   'freeze_sha':sha(frozen), 'old_checkpoint_migration':False,
                   'scope':'Start new full evidence process; completion is determined by actual child exit and receipts'}, f, indent=2)
    print(json.dumps({'starting':args.stage, 'output':str(target)}), flush=True)
    code = subprocess.call(argv, cwd=ROOT)
    with (OUT / (args.stage+'.root_exit.json')).open('x', encoding='utf8') as f:
        json.dump({'stage':args.stage, 'actual_child_exit':code, 'report_present':target.exists(),
                   'report_sha':sha(target) if target.exists() else None, 'launch_sha':sha(start)}, f, indent=2)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
