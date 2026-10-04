"""Promote exact independently reviewed joint runtime after its own full gates."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT.parent / 'unpack_work/campaign_chapter08_joint_v4_candidate'
OLD = '9ad987656683e771ea2c280e10316397efeaa5e5a7474d362c38aa18db67f54e'
NEW = '20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30'
CHANGES = {'adapters/api.py', 'content/capabilities.py', 'content/schemas.py', 'domains/abilities.py',
           'domains/buffs.py', 'domains/buff_application.py', 'domains/buff_lifetime.py', 'domains/effects.py',
           'domains/lifecycle.py', 'domains/predefined_reactivation.py', 'domains/rebirth.py',
           'domains/rebirth_self_buffs.py', 'domains/terminal_lifecycle.py', 'rules/contracts.json'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    return {path.relative_to(root).as_posix(): sha(path) for path in root.rglob('*')
            if path.is_file() and path.suffix in ('.py', '.json')}


def core(root):
    return subprocess.check_output([sys.executable, '-c',
        'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',
        str(root)], cwd=root, text=True).strip()


def bound(path, expected):
    assert sha(path) == expected, str(path)
    return json.loads(path.read_bytes())


def pins(values):
    for name, checksum in values.items():
        assert sha(name) == checksum, name


def main():
    assert core(ROOT) == OLD and core(CAND) == NEW
    suite_path = ROOT / 'validation/campaign/chapter08_joint_v4/full_suite_v2/verification.json'
    suite = bound(suite_path, '37e385c2f861209e56653aa8f172eaebf2e9223c233cf8a59ca4757f7afcbe4b')
    assert suite['passed'] and suite['exitcode'] == 0 and suite['core'] == NEW and suite['identity_stable']
    assert len(suite['cases']) == 1219 and all(case['outcome'] == 'passed' for case in suite['cases'])
    assert not suite['collection_skips'] and suite['guards_start'] == suite['guards_end']
    assert suite['all_other_1218_expectations_unchanged']
    assert suite['expectation_replacements'] == [{
        'original_nodeid': 'tests_v2/test_rules.py::test_catalog_has_98_contracts_and_is_immutable',
        'actual_function': 'tools.chapter08_joint_v2.test_catalog_v1.test_catalog_is_exact_previous98_plus_dynamic_lifetime_and_readonly'}]
    pins(suite['guards_end'])
    assert all(Path(name).is_relative_to(CAND / 'ark_sim') for name in suite['actual_modules'].values())
    baseline_path = ROOT / 'validation/campaign/chapter08_joint_v4/baseline/verification.identity.json'
    baseline = bound(baseline_path, 'b470b1346c70521b0260f7bcbc3c197cae00b04c5a329d6bd66708a272f842e8')
    assert baseline['passed'] and baseline['exit_code'] == 0 and baseline['identity_stable']
    assert baseline['implementation_sha256'] == NEW and baseline['source_at_start'] == baseline['source_at_completion']
    pins(baseline['source_at_completion'])
    independent_path = ROOT / 'validation/campaign/chapter08_joint20_independent_gate/freeze.json'
    peer = bound(independent_path, '726e3aa067c8d994cb7f052074cc0e956ecf8043f53edfbd73015e602c76cefe')
    assert peer['passed'] and peer['core'] == NEW and peer['cases'] == peer['unique_cases'] == 25 and peer['guards_equal']
    pins(peer['artifact_pins'])
    for scope in peer['scope_reports']:
        assert scope['guards_start'] == scope['guards_end']
        pins(scope['guards_end'])
    before, after = inventory(ROOT / 'ark_sim'), inventory(CAND / 'ark_sim')
    assert set(before) <= set(after) and len(after) == 101
    assert {name for name, checksum in after.items() if before.get(name) != checksum} == CHANGES
    out = ROOT / 'validation/campaign/chapter08_joint_v4_primary'
    backup = ROOT.parent / 'unpack_work/primary_9ad_before_chapter08_joint_v4'
    assert not out.exists() and not backup.exists()
    shutil.copytree(ROOT / 'ark_sim', backup / 'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    assert inventory(backup / 'ark_sim') == before and core(backup) == OLD
    for name in sorted(CHANGES):
        shutil.copyfile(CAND / 'ark_sim' / name, ROOT / 'ark_sim' / name)
    assert inventory(ROOT / 'ark_sim') == after and core(ROOT) == NEW
    out.mkdir()
    receipt = {'passed': True, 'primary_before': OLD, 'primary_after': NEW, 'changes': sorted(CHANGES),
               'before': before, 'after': after, 'backup': str(backup), 'own_full_suite_sha': sha(suite_path),
               'baseline_identity_sha': sha(baseline_path), 'independent_freeze_sha': sha(independent_path),
               'source_test_count': 1219, 'catalog_only_expectation_update': suite['expectation_replacements'],
               'scope': 'Generic dynamicBuff/selflease/reusablepredefines/finitezeroHPterminal currentcallbacklineage; no completeBoss/whole/client approval',
               'legacy_catalog_test_file_preserved_while_old_guarded_runs_finish': True}
    target = out / 'promotion.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'passed': True, 'core': NEW, 'promotion_sha': sha(target), 'files': len(after)}))


if __name__ == '__main__':
    main()
