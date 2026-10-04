"""Compose immutable generic candidates by a checked three-way byte merge.

This creates an isolated runtime only. Promotion requires that runtime's own
regressions, baseline and independent review; old receipts keep old identities.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent / 'unpack_work/campaign_content_base_v2_candidate'
BASE_CORE = 'd509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'
WAITING = ROOT.parent / 'unpack_work/campaign_waiting_actions_v2_candidate'
WAITING_CORE = 'c997d5aa71b8607ca1dc2ca8b03701fafce2d9b54a85682a44031ae3bea7da37'
WAITING_FREEZE = ROOT / 'validation/campaign/waiting_actions_v2/freeze.json'
WAITING_FREEZE_SHA = 'c5d67fcb021669ec65907cce0515d4b4f599984366c533d232d38d255c207ab3'
TILES = ROOT.parent / 'unpack_work/campaign_target_tile_facts_v1_candidate'
TILES_CORE = 'af16e21678f04bcf6ab2ca64b8829da8511bb82cffea6f5c9906fba9b1bdc0da'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def files(root):
    return {p.relative_to(root).as_posix(): sha(p)
            for p in root.rglob('*') if p.is_file()
            and p.suffix in ('.py', '.json') and '__pycache__' not in p.parts}


def core(root):
    code = ('import sys;sys.path.insert(0,sys.argv[1]);'
            'from ark_sim.adapters.api import implementation_digest;'
            'print(implementation_digest())')
    return subprocess.check_output([sys.executable, '-c', code, str(root)],
                                   cwd=root, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aura-root', type=Path, required=True)
    parser.add_argument('--aura-core', required=True)
    parser.add_argument('--aura-freeze', type=Path, required=True)
    parser.add_argument('--aura-freeze-sha', required=True)
    parser.add_argument('--output-runtime', type=Path, required=True)
    parser.add_argument('--output-report', type=Path, required=True)
    args = parser.parse_args()
    inputs = [(WAITING, WAITING_CORE), (TILES, TILES_CORE),
              (args.aura_root.resolve(), args.aura_core)]
    out = args.output_runtime.resolve()
    report = args.output_report.resolve()
    assert not out.exists() and not report.exists()
    assert sha(args.aura_freeze) == args.aura_freeze_sha
    assert sha(WAITING_FREEZE) == WAITING_FREEZE_SHA
    for path, pin in json.loads(WAITING_FREEZE.read_bytes())['files'].items():
        assert sha(path) == pin, path
    assert core(BASE) == BASE_CORE
    original = files(BASE / 'ark_sim')
    guards = {}
    for runtime, expected in inputs:
        assert core(runtime) == expected, str(runtime)
        current = files(runtime / 'ark_sim')
        assert not set(original) - set(current), 'Candidate deleted parent files'
        guards[str(runtime)] = current

    # Build all merged bytes before writing the output runtime. A conflicting
    # edit is a real stop; no hand-picked side can silently replace another.
    result = {rel: (BASE / 'ark_sim' / rel).read_bytes() for rel in original}
    merged = []
    for runtime, _ in inputs:
        for rel, pin in sorted(guards[str(runtime)].items()):
            if original.get(rel) == pin:
                continue
            incoming = (runtime / 'ark_sim' / rel).read_bytes()
            prior = result.get(rel)
            ancestor = ((BASE / 'ark_sim' / rel).read_bytes()
                        if rel in original else None)
            if prior is None or prior == ancestor or prior == incoming:
                result[rel] = incoming
                continue
            assert ancestor is not None, 'Conflicting newly added file: ' + rel
            with tempfile.TemporaryDirectory(prefix='ark-foundation-merge-') as d:
                paths = [Path(d) / name for name in ('ours', 'base', 'theirs')]
                for path, body in zip(paths, (prior, ancestor, incoming)):
                    path.write_bytes(body)
                process = subprocess.run(['git', 'merge-file', '-p',
                                          *map(str, paths)], capture_output=True)
                if process.returncode:
                    # Both candidates change exactly the inactive-source gate.
                    # Keep independently authenticated permissions and every
                    # target/visibility constraint. No other conflict is solved.
                    text = process.stdout.decode('utf8')
                    start = text.find('<<<<<<< ')
                    middle = text.find('\n=======\n', start)
                    end = text.find('\n>>>>>>> ', middle)
                    tail = text.find('\n', end + 1)
                    ours = text[text.find('\n', start)+1:middle]
                    theirs = text[middle+9:end]
                    expected_ours = "        if (not self.ctx.active(source) and not (getattr(self.ctx,'waiting_actions',None) is not None and self.ctx.waiting_actions.source_allowed(source))) or not self.ctx.active(candidate) or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):"
                    expected_theirs = "\n".join([
                        '        source_allowed=self.ctx.active(source)',
                        '        if aura_parent is not None:',
                        '            from .shared_auras import selection_source_allowed',
                        '            source_allowed=selection_source_allowed(self.ctx,source,selector,aura_parent)',
                        '        if not source_allowed or not self.ctx.active(candidate) or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):'])
                    if (rel != 'domains/movement.py' or process.returncode != 1
                            or text.count('<<<<<<< ') != 1 or ours != expected_ours
                            or theirs != expected_theirs):
                        raise RuntimeError('Unresolved three-way conflict in ' + rel)
                    resolved = "\n".join([
                        '        source_allowed=self.ctx.active(source)',
                        '        if aura_parent is not None:',
                        '            from .shared_auras import selection_source_allowed',
                        '            source_allowed=selection_source_allowed(self.ctx,source,selector,aura_parent)',
                        '        elif not source_allowed:',
                        "            waiting=getattr(self.ctx,'waiting_actions',None)",
                        '            source_allowed=waiting is not None and waiting.source_allowed(source)',
                        '        if not source_allowed or not self.ctx.active(candidate) or self.ctx.route_hidden(source) or self.ctx.route_hidden(candidate):'])
                    result[rel] = (text[:start]+resolved+'\n'+text[tail+1:]).encode('utf8')
                else:
                    result[rel] = process.stdout
            merged.append({'file': rel, 'incoming_runtime': str(runtime),
                           'prior_sha': hashlib.sha256(prior).hexdigest(),
                           'ancestor_sha': hashlib.sha256(ancestor).hexdigest(),
                           'incoming_sha': pin,
                           'merged_sha': hashlib.sha256(result[rel]).hexdigest()})

    # Inputs must still be identical after the merge process.
    assert files(BASE / 'ark_sim') == original and core(BASE) == BASE_CORE
    for runtime, expected in inputs:
        assert files(runtime / 'ark_sim') == guards[str(runtime)]
        assert core(runtime) == expected
    for rel, body in result.items():
        target = out / 'ark_sim' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    # A historical JSON read by original offline importer tests is copied as
    # data only. No V1 Python implementation is part of the candidate runtime.
    old_json = BASE / 'ark_emulator/levels/packs/level_main_00-01.json'
    if old_json.exists():
        target = out / old_json.relative_to(BASE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old_json, target)
    after = files(out / 'ark_sim')
    identity = core(out)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        'parent_core': BASE_CORE, 'core': identity, 'runtime': str(out),
        'parent_guards': original, 'input_guards': guards,
        'input_cores': {str(p): c for p, c in inputs},
        'merged_files': merged, 'output_guards': after,
        'delta': {p: {'old': original.get(p), 'new': h}
                  for p, h in after.items() if original.get(p) != h},
        'aura_freeze': {'path': str(args.aura_freeze.resolve()),
                        'sha256': args.aura_freeze_sha},
        'waiting_freeze': {'path': str(WAITING_FREEZE),
                           'sha256': WAITING_FREEZE_SHA},
        'full_suite_passed': False, 'independently_reviewed': False,
        'primary_modified': False,
    }, indent=2) + '\n', encoding='utf8', newline='')
    print(json.dumps({'core': identity, 'report_sha': sha(report),
                      'merged': [m['file'] for m in merged]}))


if __name__ == '__main__':
    main()
