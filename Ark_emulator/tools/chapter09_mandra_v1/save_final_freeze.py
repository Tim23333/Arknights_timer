"""Freeze actual same-source Mandra author gates; no simulation or promotion."""
import sys, json, hashlib, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND = (ROOT / '../unpack_work/campaign_c9_mandra_v1_candidate').resolve()
PARENT = (ROOT / '../unpack_work/campaign_c9_duspfr_v1_candidate').resolve()
sys.path.insert(0, str(CAND)); sys.path.insert(1, str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_mandra_v1.build import build, providers, PROFILE
from tools.chapter09_mandra_v1.test_author import fixture

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
OUT = ROOT / 'validation/campaign/chapter09_mandra_v1'
core = implementation_digest()
catalog = json.loads((CAND / 'ark_sim/rules/contracts.json').read_bytes())
parent_catalog = json.loads((PARENT / 'ark_sim/rules/contracts.json').read_bytes())
assert catalog['contracts'][:-1] == parent_catalog['contracts']
assert catalog['types'] == parent_catalog['types'] and len(catalog['contracts']) == 108
assert catalog['contracts'][-1]['status'] == 'declared'
reports = []
for name in ['author.final.v2.json', 'author.capture.final.v2.json',
             'author.waiting_mode.final.v2.json', 'author.domain46.final.v2.json']:
    path = OUT / name; report = json.loads(path.read_bytes())
    assert report['actual_exit'] == 0 and report['core_before'] == report['core_after'] == core
    if 'source_helpers_before' in report:
        assert report['source_helpers_before'] == report['source_helpers_after']
        assert all(sha(Path(key)) == value for key, value in report['source_helpers_before'].items())
    reports.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'actual_exit': 0})

modules = []; programs = []
for profile in PROFILE:
    content = build(profile); content.pop('scenarioDraft', None)
    path = ROOT / 'packages/campaign/chapter09_consumers/mandra' / (
        'module.v1.json' if profile == 'talent_prefix' else 'module.skill_prefix.v1.json')
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    modules.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'profile': profile})
    program = Compiler(providers=providers()).compile(fixture(profile))
    programs.append({'profile': profile, 'program_fingerprint': program.fingerprint,
                     'dependency_count': len(program.dependency_ids), 'metadata': program.to_dict()['metadata']})
public = fixture(); public['scenarioDraft']['commands'] = [
    {'at': 0, 'action': 'skill', 'source': 'player', 'ability': 'ability/m/test/hit'}]
public_fp = Compiler(providers=providers()).compile(public).fingerprint
# Observed directly from the actual raw checkpoint before wrapper cleanup.
assert public_fp == '9d72175161673602c92452a89d20e3075b577e370e6fe767e0d88720b418ae33'
actual = json.loads((OUT / 'author.final.v2.json').read_bytes())
programs.append({'profile': 'actual_public_cpp', 'program_fingerprint': public_fp,
                 'artifact': actual['artifacts'][0], 'raw_preserved': False,
                 'cpp_and_full_public_head': next(x['passed'] for x in actual['results'] if x['case'] == 'public_cpp_head')})

source_before = {}; delta = []
for path in sorted((CAND / 'ark_sim').rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc': continue
    rel = path.relative_to(CAND); source_before[rel.as_posix()] = sha(path); old = PARENT / rel
    if not old.exists() or old.read_bytes() != path.read_bytes():
        saved = ROOT / 'tools/chapter09_mandra_v1/source_delta.final.v1' / rel
        saved.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, saved)
        delta.append({'path': rel.as_posix(), 'parent_sha256': sha(old) if old.exists() else None,
                      'candidate_sha256': sha(path), 'saved_delta_path': saved.relative_to(ROOT).as_posix(),
                      'saved_delta_sha256': sha(saved)})
cleanup = []
for run in ['chapter09_mandra_final_author_v2', 'chapter09_mandra_capture_final_v2',
            'chapter09_mandra_waiting_final_v2', 'chapter09_mandra_domain46_final_v2']:
    path = Path('E:/ArkSimLogs/receipts') / run / 'completion.json'; data = json.loads(path.read_bytes())
    assert data['worker_exit'] == data['cleanup_exit'] == 0 and data['raw_logs_removed_after_validation']
    assert data['cleanup_result']['remaining_files'] == data['cleanup_result']['error_count'] == 0
    saved = OUT / ('cleanup.' + run + '.json'); saved.write_bytes(path.read_bytes())
    cleanup.append({'path': saved.relative_to(ROOT).as_posix(), 'sha256': sha(saved),
                    'reclaimed_bytes': data['cleanup_result']['reclaimed_bytes'], 'remaining_files': 0, 'error_count': 0})
source_after = {rel: sha(CAND / rel) for rel in source_before}
assert source_before == source_after and implementation_digest() == core
receipt = {'schema': 'ark-sim/source-candidate-freeze/v1', 'candidate': str(CAND), 'parent': str(PARENT),
    'parent_core': '2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0',
    'core_before': core, 'core_after': implementation_digest(), 'final_freeze': True, 'promoted': False,
    'source_before': source_before, 'source_after': source_after,
    'helpers': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT/'tools/chapter09_mandra_v1').glob('*.py'))},
    'catalog': {'count': 108, 'sha256': sha(CAND/'ark_sim/rules/contracts.json'),
                'old107_and_types_equal': True, 'appended_row': catalog['contracts'][-1]},
    'modules': modules, 'programs': programs, 'reports': reports, 'source_delta': delta,
    'source_delta_files': len(delta), 'author_groups': 12, 'domain46_original_tests': 46,
    'generic_capture_and_owned_waiting_groups': 2, 'cleanup': cleanup,
    'reclaimed_bytes': sum(x['reclaimed_bytes'] for x in cleanup), 'remaining_files': 0, 'error_count': 0,
    'historical_failures_preserved': [p.relative_to(ROOT).as_posix() for p in sorted(OUT.glob('development.*.json'))]
        + [p.relative_to(ROOT).as_posix() for p in sorted(OUT.glob('parent.*counter.json'))],
    'correction_notes': {
        'highest_ATK': 'Actual v3 content failure: lowest score ordering required negative effective ATK. Final50+3000 outranks1000; expected unchanged.',
        'pending_control': 'Original actual control failure retained. Default strict; finite explicit skip retries only ActivationRejected; actual started/current cast clears request.',
        'tile_authority': 'Original real copied active cast, no task, created1token. New strict task opt-in rejects exact task error; real task subsequently spawns.',
        'catalog_encoding': 'Finalv1 JSON guard superseded; exact parent107 row81 description restored. Finalv2 gates bind corrected JSON and full old107/types equality.'},
    'scope': 'Complete source-declared four-mode consumer with explicit reference geometry, harpoon, named-null branch placement/direction, same-hit pillar break timing and empty-action animation policy. Native method bodies/client fidelity remain unverified.',
    'pending_gates': ['Independent peer', 'Full1219+108 catalog', 'Production baseline', 'Root promotion']}
path = OUT/'freeze.final.v1.json'; assert not path.exists()
path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(json.dumps({'core': core, 'freeze': path.relative_to(ROOT).as_posix(), 'freeze_sha256': sha(path),
                  'modules': modules, 'delta_files': len(delta), 'reclaimed_bytes': receipt['reclaimed_bytes'],
                  'remaining_files': 0, 'error_count': 0}))
