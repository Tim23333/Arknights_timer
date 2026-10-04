"""Save final focused checks and actual runtime/tool identities."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'validation/campaign/m71_event_storage'
spec = importlib.util.spec_from_file_location('m71_build', ROOT/'tools/candidates/m71_event_storage/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    source_root = build.OUT/'ark_sim'
    core = build.core(build.OUT)
    composition = {'parent_core': build.core(build.BASE), 'core': core,
        'source_sha256': {str(p.relative_to(build.OUT)): sha(p) for p in sorted(source_root.rglob('*.py'))},
        'offline_fixture_sha256': sha(build.OUT/'ark_emulator/levels/packs/level_main_00-01.json')}
    assert composition['parent_core'] == '1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
    (OUT/'composition.json').write_text(json.dumps(composition, indent=2)+'\n', encoding='utf8')
    bootstrap = "import sys,pytest;sys.path.insert(0,"+repr(str(build.OUT))+ ");sys.exit(pytest.main(['tests_v2/test_kernel.py','tests_v2/test_ark_import.py','tools/experiments/m71_event_storage/test_storage.py','-q']))"
    result = subprocess.run([sys.executable, '-c', bootstrap], cwd=ROOT, capture_output=True, text=True)
    log = result.stdout + result.stderr
    (OUT/'focused-tests.log').write_text(log, encoding='utf8')
    if result.returncode:
        raise RuntimeError(log)
    for script in ('benchmark.py', 'compare_parent.py'):
        completed = subprocess.run([sys.executable, str(Path(__file__).with_name(script))], cwd=ROOT,
                                   capture_output=True, text=True)
        (OUT/(script+'.log')).write_text(completed.stdout+completed.stderr, encoding='utf8')
        if completed.returncode:
            raise RuntimeError(completed.stdout+completed.stderr)
    benchmark = json.loads((OUT/'benchmark.json').read_text(encoding='utf8'))
    assert benchmark['core'] == core
    report = {'passed': True, 'core': core, 'parent_core': composition['parent_core'],
        'focused_test_summary': log.strip().splitlines()[-1],
        'benchmark': 'benchmark.json', 'no_opt_parent_comparison': 'parent-no-opt-comparison.json',
        'scope': 'Storage boundaries and actual bounded source traces; broad fullsuite and fullstage not verified',
        'tools_sha256': {str(p.relative_to(ROOT)): sha(p)
            for folder in ('tools/candidates/m71_event_storage', 'tools/experiments/m71_event_storage')
            for p in sorted((ROOT/folder).glob('*')) if p.is_file()}}
    (OUT/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
