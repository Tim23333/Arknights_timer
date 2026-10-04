"""Preview or delete completed simulation artifacts, preserving source inputs."""
import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = Path(__file__).with_name('simulation_log_policy.json')
SKIP = {'.git', '__pycache__', 'node_modules', '.venv'}
INPUT_KEYS = {'schemaVersion', 'manifest', 'definitions', 'scenarioDraft', 'native_document',
              'prefab', 'BSON', 'bson_templates', 'source_locks', 'source_pins', 'variants'}
ARTIFACT_KEYS = {'checkpoint', 'events', 'snapshot', 'scheduler', 'world', 'kernel', 'capture',
                 'observations', 'replay', 'restored', 'forward', 'head', 'continued'}


def within(path, roots):
    path = Path(path).resolve()
    return any(path.is_relative_to(Path(root).resolve()) for root in roots)


def processes():
    if os.name != 'nt':
        return []
    command = "Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(python|pythonw).*\\.exe$'} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    raw = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True, encoding='utf8')
    rows = json.loads(raw) if raw.strip() else []
    return rows if isinstance(rows, list) else [rows]


def protections(policy, rows):
    folders = [Path(path).resolve() for path in policy.get('protected_paths', [])]
    stems = []
    for row in rows:
        command = row.get('CommandLine') or ''
        for flag in ('output', 'evidence'):
            found = re.search(r'--' + flag + r'\s+(?:"([^"]+)"|(\S+))', command)
            if found:
                value = found.group(1) or found.group(2)
                path = Path(value)
                if not path.is_absolute():
                    path = ROOT / path
                path = path.resolve()
                if flag == 'output':
                    folders.append(path.parent)
                else:
                    stems.append(path.with_suffix(''))
    return folders, stems


def locked(path):
    if os.name != 'nt':
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        return True
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle(handle)
    return False


def classify(path, roots):
    name = path.name.lower()
    if path.is_symlink() or not within(path, roots):
        return None
    if name.endswith(('.jsonl', '.log')) or '.jsonl.' in name:
        return 'event_or_terminal_log'
    if path.suffix.lower() != '.json':
        return None
    if any(part == 'packages' for part in path.parts):
        # Content/source files may use arbitrary first keys. Only recognisable
        # output names inside explicit evidence directories are disposable.
        evidence_dir = any(re.search(r'(evidence|captures|independent|_author|_boundaries|_clocks|required_|ore_mine_joint|retained_)', part)
                           for part in path.parts[:-1])
        output_name = bool(re.search(r'(events|checkpoint|capture|observations|replay|report)', name))
        if not evidence_dir or not output_name:
            return None
    # Compact verification receipts can mention checkpoints or captures in
    # their filenames; they are summaries rather than disposable raw records.
    if path.stat().st_size <= 1024 * 1024 and any(word in name for word in ('result', 'verification', 'freeze', 'report', 'guard', 'pin', 'rejection')):
        return None
    if re.search(r'(?:^|[._-])(checkpoint|captures?|events|observations)(?:[._-]|$)', name):
        return 'checkpoint_or_event_capture'
    if name.endswith('.replay.json') or name == 'replay.json':
        return 'replay_operation_log'
    if path.stat().st_size <= 1024 * 1024:
        return None
    with path.open('rb') as stream:
        prefix = stream.read(16384).decode('utf8', errors='replace')
    keys = set(re.findall(r'"([^"\\]+)"\s*:', prefix))
    if name in {'input.json', 'commands.json'}:
        return None
    # Top-level source packages and native documents are retained. Runtime
    # reports may contain nested input snapshots, so inspect their first key.
    first_key = re.match(r'\s*\{\s*"([^"\\]+)"\s*:', prefix)
    if first_key and first_key.group(1) in INPUT_KEYS:
        return None
    if ARTIFACT_KEYS & keys or re.search(r'(forward|restored|head|live|snapshot|\.cp\.)', name):
        return 'large_runtime_capture'
    # Large validation reports often nest hundreds of complete events. Keep
    # their compact top-level result elsewhere before deleting these captures.
    if any(part in {'validation', 'ArkSimEvidence'} for part in path.parts):
        return 'large_validation_payload'
    return None


def walk(roots):
    seen = set()
    for root in roots:
        for folder, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if name not in SKIP and not (Path(folder) / name).is_symlink()]
            for name in files:
                path = (Path(folder) / name).resolve()
                if path not in seen:
                    seen.add(path)
                    yield path


def plan(policy, roots, rows, age):
    folders, stems = protections(policy, rows)
    candidates, retained = [], []
    now = time.time()
    for path in walk(roots):
        try:
            reason = classify(path, roots)
            if not reason:
                continue
            stat = path.stat()
            protect = next((str(folder) for folder in folders if path.is_relative_to(folder)), None)
            protect = protect or next((str(stem) for stem in stems if path.parent == stem.parent and path.name.startswith(stem.name)), None)
            if protect or now - stat.st_mtime < age * 60 or locked(path):
                retained.append({'path': str(path), 'bytes': stat.st_size,
                                 'reason': 'live_process_or_explicit_protection' if protect else 'recent_or_open'})
            else:
                candidates.append({'path': str(path), 'bytes': stat.st_size,
                                   'mtime_ns': stat.st_mtime_ns, 'kind': reason})
        except OSError as error:
            retained.append({'path': str(path), 'reason': str(error)})
    return candidates, retained


def execute(candidates, roots):
    deleted, errors = [], []
    # No recursive directory deletion. Revalidate each exact absolute file.
    for record in candidates:
        path = Path(record['path']).resolve()
        try:
            assert within(path, roots) and not path.is_symlink()
            stat = path.stat()
            if stat.st_size != record['bytes'] or stat.st_mtime_ns != record['mtime_ns'] or locked(path):
                raise ValueError('File changed or opened after preview')
            path.unlink()
            deleted.append(record)
        except (OSError, ValueError, AssertionError) as error:
            errors.append({'path': str(path), 'reason': str(error)})
    return deleted, errors


def compact_receipts(candidates, destination):
    """Keep small status/identity fields from large reports, never full traces."""
    destination.mkdir(parents=True, exist_ok=True)
    keep = {'schema', 'status', 'passed', 'exit_code', 'exitcode', 'actual_exit', 'core',
            'implementation', 'implementation_sha256', 'identity_stable', 'guards_equal',
            'process_complete', 'checkpoint_equal', 'durable_checkpoint_equal', 'replay_equal',
            'scope', 'client_verified', 'actual_game_accuracy_verified', 'seconds', 'elapsed_seconds'}
    for record in candidates:
        if record['kind'] not in {'large_runtime_capture', 'large_validation_payload'} or record['bytes'] > 600*1024*1024:
            continue
        try:
            value = json.loads(Path(record['path']).read_bytes())
            if not isinstance(value, dict):
                continue
            summary = {key: item for key, item in value.items() if key in keep
                       and isinstance(item, (str, int, float, bool, type(None)))}
            if not summary:
                continue
            summary.update(original_path=record['path'], original_bytes=record['bytes'],
                           raw_payload_deleted_by_user_policy=True,
                           status_extracted_before_deletion=True, fresh_validation_performed=False)
            label = hashlib.sha256(record['path'].encode()).hexdigest()[:20]
            (destination/(label+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        except (OSError, ValueError):
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Delete eligible completed logs; default previews')
    parser.add_argument('--legacy', action='store_true', help='Also clean configured previous output locations')
    parser.add_argument('--run-dir', type=Path, help='One completed run inside the fixed log root')
    parser.add_argument('--completed-pid', type=int, help='Ignore the current completing worker PID only')
    parser.add_argument('--minimum-age-minutes', type=float)
    args = parser.parse_args()
    policy = json.loads(POLICY.read_bytes())
    log_root = Path(policy['log_root']).resolve()
    roots = [log_root / 'runs']
    if args.legacy:
        roots += [Path(path).resolve() for path in policy['legacy_roots']]
    if args.run_dir:
        if not args.run_dir.resolve().is_relative_to(log_root / 'runs'):
            raise ValueError('Run must be inside configured log_root/runs')
        roots = [args.run_dir.resolve()]
    rows = [row for row in processes() if row['ProcessId'] != args.completed_pid]
    age = args.minimum_age_minutes if args.minimum_age_minutes is not None else policy['minimum_age_minutes']
    if age < 0:
        raise ValueError('Age must be nonnegative')
    candidates, retained = plan(policy, roots, rows, age)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report_root = log_root / 'cleanup'
    report_root.mkdir(parents=True, exist_ok=True)
    target = report_root / (stamp + ('.deleted.json' if args.apply else '.preview.json'))
    report = {'apply': args.apply, 'roots': [str(root) for root in roots], 'eligible_files': len(candidates),
              'eligible_bytes': sum(record['bytes'] for record in candidates), 'candidates': candidates,
              'protected': retained, 'log_root': str(log_root), 'policy_sha': hashlib.sha256(POLICY.read_bytes()).hexdigest()}
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    if args.apply:
        compact_receipts(candidates, log_root/'receipts'/'legacy_compact')
        deleted, errors = execute(candidates, roots)
        report.update(deleted_files=len(deleted), reclaimed_bytes=sum(record['bytes'] for record in deleted), errors=errors)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: report[key] for key in ('apply', 'eligible_files', 'eligible_bytes', 'log_root')} | {
        'deleted_files': report.get('deleted_files', 0), 'reclaimed_bytes': report.get('reclaimed_bytes', 0),
        'protected_files': len(retained), 'report': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
