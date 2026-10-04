"""Run M21 with the complete offline/current-content test inputs and catalog83."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT.parent/'unpack_work/campaign_m21_integration_candidate'
CORE = 'c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e'
sys.path.insert(0, str(RUNTIME)); sys.path.insert(1, str(ROOT)); sys.path.insert(2, str(ROOT/'tests_v2'))


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--targeted', action='store_true'); args = parser.parse_args()
    os.environ['CAMPAIGN_SUMMON_PACKAGE'] = str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
    os.environ['ARKSIM_M10_REVIEW_ROOT'] = str(RUNTIME)
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent != RUNTIME/'ark_sim' or implementation_digest() != CORE: raise RuntimeError('wrong frozen integrated runtime')
    original = ROOT/'tests_v2/test_rules.py'; clone = ROOT/'tools/experiments/m21_catalog/test_rules.py'; clone.parent.mkdir(parents=True, exist_ok=True)
    source = original.read_bytes(); updated = source.replace(b'test_catalog_has_82_contracts_and_is_immutable', b'test_catalog_has_83_contracts_and_is_immutable').replace(b'len(DEFAULT_CATALOG["contracts"]) == 82', b'len(DEFAULT_CATALOG["contracts"]) == 83')
    updated = updated.replace(b'Path(__file__).parents[1] / "docs/v2_examples/custom_guard.json"', b'Path(__file__).parents[3] / "docs/v2_examples/custom_guard.json"')
    if source == updated or source.count(b'len(DEFAULT_CATALOG["contracts"]) == 82') != 1: raise ValueError('unexpected original catalog test source')
    clone.write_bytes(updated)
    # Same numerical/rule assertions, except the new explicitly introduced contract
    # count. Keep the original primary test bytes and the original failed run.
    report_dir = ROOT/'validation/campaign/m21_integration'; report_dir.mkdir(exist_ok=True)
    copy_record = {'original_sha256': sha(original), 'copy_sha256': sha(clone), 'expected_catalog': 83,
        'new_contract': 'terrain.tile_options', 'only_changes': ['function count label82->83', 'count expectation82->83', 'same repo sample path after test relocation'], 'original_unchanged': True}
    (report_dir/'catalog_test_copy.json').write_text(json.dumps(copy_record, indent=2)+'\n', encoding='utf8', newline='\n')
    selection = ['tests_v2/test_ark_import.py', 'tests_v2/test_canonical_kalts.py', 'tests_v2/test_canonical_night.py',
        'tests_v2/test_canonical_weedy.py', 'tests_v2/test_m10_resource_precision_review.py', str(clone)] if args.targeted else [
        'tests_v2', '--ignore=tests_v2/test_rules.py', str(clone), 'tools/experiments/m21', 'tools/experiments/m20/test_dormant.py',
        'tools/experiments/m20_source/test_source_boundary.py', 'tools/experiments/m20/test_native_npc.py', 'tools/experiments/m16_root_peer/test_terrain_review.py']
    sources = {str(p): sha(p) for p in (Path(__file__), original, clone, Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']), RUNTIME/'ark_sim/rules/contracts.json')}
    before = implementation_digest()
    print(json.dumps({'runtime': ark_sim.__file__, 'core': before, 'source_at_start': sources, 'selected': selection,
        'content_inputs': {k: os.environ[k] for k in ('CAMPAIGN_SUMMON_PACKAGE', 'ARKSIM_M10_REVIEW_ROOT')}}), flush=True)
    import pytest
    code = int(pytest.main([*selection, '-q']))
    after = implementation_digest(); stable = before == after == CORE and all(sha(Path(p)) == value for p, value in sources.items())
    result = {'schema': 'ark-sim/integrated-suite-with-inputs/v1', 'passed': code == 0 and stable, 'exit_code': code,
        'implementation_before': before, 'implementation_after': after, 'source_at_start': sources,
        'source_at_completion': {p: sha(Path(p)) for p in sources}, 'identity_stable': stable,
        'actual_runtime': ark_sim.__file__, 'selection': selection, 'formal_approved': False,
        'content_inputs': {k: os.environ[k] for k in ('CAMPAIGN_SUMMON_PACKAGE', 'ARKSIM_M10_REVIEW_ROOT')}}
    output = report_dir/('targeted_input_corrected_20261003.json' if args.targeted else 'full_input_corrected_20261003.json')
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8', newline='\n')
    if not result['passed']: raise SystemExit(1)


if __name__ == '__main__': main()
