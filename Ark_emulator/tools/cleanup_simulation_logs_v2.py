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
FIXED_LOG_ROOT = Path('E:/ArkSimLogs').resolve()
SKIP = {'.git', '__pycache__', 'node_modules', '.venv'}
INPUT_KEYS = {'schemaVersion', 'manifest', 'definitions', 'scenarioDraft', 'native_document',
              'prefab', 'BSON', 'bson_templates', 'source_locks', 'source_pins', 'variants'}
ARTIFACT_KEYS = {'checkpoint', 'events', 'snapshot', 'scheduler', 'world', 'kernel', 'capture',
                 'observations', 'replay', 'restored', 'forward', 'head', 'continued'}


class ResolvedRoots(tuple):
    """Freeze canonical allowed directories once per cleanup operation."""
    def __new__(cls, roots):
        return super().__new__(cls, (Path(root).resolve() for root in roots))


def within(path, roots):
    path = Path(path).resolve()
    if isinstance(roots, ResolvedRoots):
        return any(path.is_relative_to(root) for root in roots)
    return any(path.is_relative_to(Path(root).resolve()) for root in roots)


def processes():
    if os.name != 'nt':
        return []
    command = "Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(python|pythonw).*\\.exe$'} | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    raw = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True, encoding='utf8')
    rows = json.loads(raw) if raw.strip() else []
    return rows if isinstance(rows, list) else [rows]

def active_processes(ignored_pids):
    rows=processes();by_pid={row['ProcessId']:row for row in rows};ignored=set(ignored_pids)
    def tail(command):
        match=re.match(r'^\s*(?:"[^"]*"|\S+)\s*(.*)$',command or '')
        return match.group(1) if match else None
    # Windows venv launchers stay alive while the actual Python child runs.
    # Only an exact-argv parent of a known completing/self PID is excluded.
    for pid in list(ignored):
        row=by_pid.get(pid)
        while row is not None:
            parent=by_pid.get(row.get('ParentProcessId'))
            if parent is None or not tail(row.get('CommandLine')) or tail(parent.get('CommandLine'))!=tail(row.get('CommandLine')):break
            ignored.add(parent['ProcessId']);row=parent
    return [row for row in rows if row['ProcessId'] not in ignored]


def protections(policy, rows):
    folders = [Path(path).resolve() for path in policy.get('protected_paths', [])]
    stems = []
    for row in rows:
        command = row.get('CommandLine') or ''
        pattern = r'(?:^|\s)--(output|evidence|run-dir|basetemp|prior)(?:\s*=\s*|\s+)(?:"([^"]+)"|\x27([^\x27]+)\x27|(\S+))'
        for found in re.finditer(pattern, command):
                flag = found.group(1)
                value = found.group(2) or found.group(3) or found.group(4)
                path = Path(value)
                if not path.is_absolute():
                    path = ROOT / path
                path = path.resolve()
                if flag == 'output':
                    folders.append(path.parent)
                elif flag == 'evidence':
                    stems.append(path.with_suffix(''))
                elif flag == 'prior':
                    # Prior reports/checkpoints can refer to the entire sealed
                    # journal family in their directory, not only this file.
                    folders.append(path if path.is_dir() else path.parent)
                else:
                    folders.append(path)
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

def linked(path):
    path = Path(path).absolute()
    return any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()) for p in (path, *path.parents))

def pid_stamp(pid):
    """Process creation identity, so an orphan run lease cannot match reused PID."""
    if type(pid) is not int or pid<1:return None
    if os.name!='nt':
        try:os.kill(pid,0);return pid
        except OSError:return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    values=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.POINTER(ctypes.c_ulonglong)]*4)]
    kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    try:
        exit_code=ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)) or exit_code.value!=259:return None
        return values[0].value if kernel.GetProcessTimes(handle,*[ctypes.byref(v) for v in values]) else None
    finally:kernel.CloseHandle(handle)

def lease_folders(roots):
    folders=[]
    for path in walk(roots):
        if path.name!='run.lease.json' or linked(path):continue
        try:
            if path.stat().st_size>65536:folders.append(path.parent);continue
            lease=json.loads(path.read_bytes())
            if lease.get('completed') is True:continue
            workers=lease.get('workers',[{'pid':lease.get('worker_pid'),'stamp':lease.get('worker_stamp')}])
            if not isinstance(workers,list) or not workers or any(
                    not isinstance(worker,dict) or type(worker.get('pid')) is not int
                    or worker['pid']<1 or type(worker.get('stamp')) is not int
                    or worker['stamp']<1 for worker in workers):
                folders.append(path.parent);continue
            if any(pid_stamp(worker['pid'])==worker['stamp'] for worker in workers):folders.append(path.parent)
        except (OSError,ValueError,AttributeError):folders.append(path.parent)
    return folders

def root_fields(prefix):
    """Bounded lexical top-level keys; nested runtime input copies are distinct."""
    decoder=json.JSONDecoder();depth=0;i=0
    while i<len(prefix):
        c=prefix[i]
        if c=='"':
            try:value,end=decoder.raw_decode(prefix,i)
            except ValueError:return
            j=end
            while j<len(prefix) and prefix[j].isspace():j+=1
            if depth==1 and j<len(prefix) and prefix[j]==':' and isinstance(value,str):
                yield value,j+1
            i=end;continue
        if c in '{[':depth+=1
        elif c in '}]':depth-=1
        i+=1


def temporary_run_artifact(path, roots):
    """Disposable test copies under the fixed run root, never repository sources."""
    path = Path(path).resolve()
    runs = FIXED_LOG_ROOT / 'runs'
    if not path.is_relative_to(runs):
        return False
    parts = path.relative_to(runs).parts
    # First component is the individual run. Restrict broad file cleanup to
    # explicitly temporary descendants; inputs elsewhere retain source guards.
    run = runs / parts[0] if parts else runs
    allowed = isinstance(roots, ResolvedRoots) and roots or ResolvedRoots(roots)
    explicitly_scoped_run = any(run.is_relative_to(root) for root in allowed)
    return explicitly_scoped_run and len(parts) >= 3 and any(
        part in {'temp', 'tmp', 'tests', 'test-tmp'} or part.startswith('pytest-of-')
        for part in parts[1:-1]
    )


def classify(path, roots):
    name = path.name.lower()
    if linked(path) or not within(path, roots):
        return None
    if temporary_run_artifact(path, roots):
        return 'temporary_run_artifact'
    if name.endswith(('.jsonl', '.log')) or '.jsonl.' in name:
        return 'event_or_terminal_log'
    if path.suffix.lower() != '.json':
        return None
    if name in {'input.json','commands.json'}:
        return None
    with path.open('rb') as stream:
        prefix=stream.read(65536).decode('utf8',errors='replace')
    top_keys={key for key,_ in root_fields(prefix)}
    if INPUT_KEYS & top_keys:
        return None
    fields=dict(root_fields(prefix));schema=None
    if 'schema' in fields:
        try:schema,_=json.JSONDecoder().raw_decode(prefix,fields['schema']+len(prefix[fields['schema']:])-len(prefix[fields['schema']:].lstrip()))
        except ValueError:pass
    if isinstance(schema,str) and (schema.startswith('ark-sim/session-checkpoint/') or schema.startswith('ark-sim/kernel-checkpoint/') or schema.startswith('ark-sim/replay/')):
        return 'checkpoint_or_event_capture' if 'checkpoint' in schema else 'replay_operation_log'
    if {'time','seconds','scenario','program_fingerprint','runtime_fingerprint','entities'} <= top_keys:
        return 'runtime_snapshot'
    # Status-only receipts can have historical capture names. A filename alone
    # must not delete their small proof or cleanup summary. Raw schema/snapshot
    # recognition above still takes precedence over this guard.
    receipt_keys={'passed','actual_exit','core','core_before','implementation',
                  'actual_full_CPP_head_equal','cleanup_exit','reclaimed_bytes','eligible_files'}
    if path.stat().st_size<=1024*1024 and receipt_keys & top_keys and not ARTIFACT_KEYS & top_keys:
        return None
    if re.search(r'(?:^|[._-])(source|native|module|plan|requirements|catalog)(?:[._-]|$)',name):
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
            dirs[:] = [name for name in dirs if name not in SKIP and not linked(Path(folder)/name)]
            for name in files:
                path = (Path(folder) / name).absolute()
                if path not in seen:
                    seen.add(path)
                    yield path


def legacy_roots(policy):
    roots = [Path(path).resolve() for path in policy.get('legacy_roots', [])]
    # Candidates and backups copied runtime validation logs along with code.
    # Only scan that known output subtree, never the native extraction tree.
    copied = policy.get('legacy_copied_validation_root')
    if copied:
        base = Path(copied).absolute()
        if linked(base):
            raise ValueError('Copied validation root must not be linked')
        for pattern in ('*/ark_sim/validation', '*/*/ark_sim/validation'):
            for path in base.glob(pattern):
                if path.is_dir() and not linked(path) and within(path, [base]):
                    roots.append(path.resolve())
    return roots


def plan(policy, roots, rows, age):
    roots = roots if isinstance(roots, ResolvedRoots) else ResolvedRoots(roots)
    folders, stems = protections(policy, rows)
    folders+=lease_folders(roots)
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
                                   'mtime_ns': stat.st_mtime_ns, 'device':stat.st_dev, 'inode':stat.st_ino, 'kind': reason})
        except OSError as error:
            retained.append({'path': str(path), 'reason': str(error)})
    return candidates, retained


def execute(candidates, roots, policy=None, rows=None, row_supplier=None):
    roots = roots if isinstance(roots, ResolvedRoots) else ResolvedRoots(roots)
    deleted, errors = [], []
    # No recursive directory deletion. Revalidate each exact absolute file.
    folders,stems=protections(policy or {},processes() if rows is None else rows)
    folders+=lease_folders(roots)
    refresh_at=0
    for record in candidates:
        path = Path(record['path']).absolute()
        try:
            if row_supplier is not None and time.monotonic()>=refresh_at:
                folders,stems=protections(policy or {},row_supplier());folders+=lease_folders(roots);refresh_at=time.monotonic()+.5
            if not within(path, roots) or linked(path):
                raise ValueError('Deletion target outside allowed roots or linked')
            if any(path.resolve().is_relative_to(folder) for folder in folders) or any(path.parent.resolve()==stem.parent and path.name.startswith(stem.name) for stem in stems):
                raise ValueError('File became protected after preview')
            stat = path.stat()
            if (stat.st_size != record['bytes'] or stat.st_mtime_ns != record['mtime_ns']
                    or stat.st_dev != record.get('device',stat.st_dev) or stat.st_ino != record.get('inode',stat.st_ino)
                    or locked(path) or classify(path,roots)!=record['kind']):
                raise ValueError('File changed or opened after preview')
            path.unlink()
            deleted.append(record)
        except FileNotFoundError:
            continue
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
        if record['kind'] not in {'large_runtime_capture', 'large_validation_payload'}:
            continue
        try:
            with Path(record['path']).open('rb') as stream:prefix=stream.read(65536).decode('utf8',errors='replace')
            summary={}
            for key,start in root_fields(prefix):
                if key not in keep:continue
                try:item,_=json.JSONDecoder().raw_decode(prefix,start+len(prefix[start:])-len(prefix[start:].lstrip()))
                except ValueError:continue
                if isinstance(item,(str,int,float,bool,type(None))):summary[key]=item
            if not summary:
                continue
            summary.update(original_path=record['path'], original_bytes=record['bytes'],
                           raw_payload_deleted_by_user_policy=False,
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
    parser.add_argument('--result-json',type=Path,help='Write a compact trusted cleanup result outside raw capture files')
    args = parser.parse_args()
    policy = json.loads(POLICY.read_bytes())
    log_root = Path(policy['log_root']).resolve()
    if log_root != FIXED_LOG_ROOT:
        raise ValueError('Cleanup log root must be the fixed E:/ArkSimLogs directory')
    roots = [log_root / 'runs']
    if args.legacy:
        roots += legacy_roots(policy)
    if args.run_dir:
        if not args.run_dir.resolve().is_relative_to(log_root / 'runs'):
            raise ValueError('Run must be inside configured log_root/runs')
        roots = [args.run_dir.resolve()]
    ignored_pids={os.getpid(),args.completed_pid}
    rows = active_processes(ignored_pids)
    age = args.minimum_age_minutes if args.minimum_age_minutes is not None else policy['minimum_age_minutes']
    if age < 0:
        raise ValueError('Age must be nonnegative')
    if not __import__('math').isfinite(age):raise ValueError('Age must be finite')
    if args.result_json:
        result=args.result_json.absolute()
        if (linked(result) or result.exists() or result.suffix.lower()!='.json'
                or result.name.lower() in {'input.json','commands.json'}
                or not any(result.resolve().is_relative_to(log_root/name) for name in ('receipts','cleanup'))):
            raise ValueError('Result JSON must be a new unlinked JSON file inside fixed receipts/cleanup directories')
        policy={**policy,'protected_paths':[*policy.get('protected_paths',[]),str(args.result_json.resolve())]}
    roots = ResolvedRoots(roots)
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
        active_rows=lambda:active_processes(ignored_pids)
        deleted, errors = execute(candidates, roots,policy,active_rows(),row_supplier=active_rows)
        for record in deleted:
            label=hashlib.sha256(record['path'].encode()).hexdigest()[:20]
            receipt=log_root/'receipts'/'legacy_compact'/(label+'.json')
            if receipt.exists():
                value=json.loads(receipt.read_bytes());value['raw_payload_deleted_by_user_policy']=True
                receipt.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        report.update(deleted_files=len(deleted), reclaimed_bytes=sum(record['bytes'] for record in deleted), errors=errors)
        remaining,retained=plan(policy,roots,active_rows(),age)
        report.update(remaining_candidates=remaining,retained=retained,
            fully_cleaned=not errors and not remaining and not retained)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    result={key: report[key] for key in ('apply', 'eligible_files', 'eligible_bytes', 'log_root')} | {
        'deleted_files': report.get('deleted_files', 0), 'reclaimed_bytes': report.get('reclaimed_bytes', 0),
        'protected_files':len(report.get('retained',report['protected'])), 'remaining_files':len(report.get('remaining_candidates',[])),
        'error_count':len(report.get('errors',[])), 'fully_cleaned':report.get('fully_cleaned',False),
        'actual_exit':2 if report.get('errors') else 0, 'report':str(target)}
    if args.result_json:
        args.result_json.parent.mkdir(parents=True,exist_ok=True)
        args.result_json.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))
    return result['actual_exit']


if __name__ == '__main__':
    raise SystemExit(main())
