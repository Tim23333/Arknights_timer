"""Run complete V2 suite with explicit current inputs under frozen M29."""
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'
CORE='a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
    os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.rules.catalog import load_catalog
    if Path(ark_sim.__file__).resolve().parent!=RUNTIME/'ark_sim' or implementation_digest()!=CORE:raise ValueError('Wrong fullsuite runtime')
    catalog=load_catalog();count=len(catalog['contracts'])
    expected_new={'terrain.tile_options','behavior.decision','selector.eligibility','targeting.eligibility','tile.contact','area.members'}
    if count!=88 or not expected_new<=set(catalog['contracts']):raise ValueError('Unexpected actual expanded contract catalog')
    source=ROOT/'tests_v2/test_rules.py';clone=ROOT/'tools/experiments/m48_integration/test_rules_catalog.py';raw=source.read_bytes()
    if raw.count(b'len(DEFAULT_CATALOG["contracts"]) == 82')!=1:raise ValueError('Primary catalogtest shape drift')
    updated=raw.replace(b'test_catalog_has_82_contracts_and_is_immutable',b'test_catalog_has_88_contracts_and_is_immutable').replace(b'len(DEFAULT_CATALOG["contracts"]) == 82',b'len(DEFAULT_CATALOG["contracts"]) == 88')
    updated=updated.replace(b'Path(__file__).parents[1] / "docs/v2_examples/custom_guard.json"',b'Path(__file__).parents[3] / "docs/v2_examples/custom_guard.json"')
    clone.write_bytes(updated);out=ROOT/'validation/campaign/m48_integration';copy={'source_sha256':sha(source),'copy_sha256':sha(clone),
        'only_changes':['catalog function label/count82->86 for4newactual contracts','same docs fixture path after relocation'],'primary_unchanged':True}
    (out/'catalog_test_copy.json').write_text(json.dumps(copy,indent=2)+'\n',encoding='utf8',newline='\n')
    selection=['tests_v2','--ignore=tests_v2/test_rules.py',str(clone),'tools/experiments/m38/test_storage.py','tools/experiments/m38/test_refs.py','tools/experiments/m38/test_fields.py','tools/experiments/m38/test_static_owner.py','tools/experiments/m38/test_overrides.py','tools/experiments/m38/test_board_scope.py','tools/experiments/m38/test_role.py',
        'tools/experiments/m48_integration', 'tools/experiments/m26_content/test_composition.py','tools/experiments/m23','tools/experiments/chapter02_tiles']
    guards=[Path(__file__),source,clone,Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']
    before={str(p.resolve()):sha(p) for p in guards}
    print(json.dumps({'core':CORE,'actual_runtime':ark_sim.__file__,'selection':selection,'source_at_start':before}),flush=True)
    code=int(pytest.main([*selection,'-q','--tb=short']))
    after={str(p.resolve()):sha(p) for p in guards};stable=before==after and implementation_digest()==CORE
    report={'schema':'ark-sim/integrated-fullsuite/v1','passed':code==0 and stable,'exit_code':code,'core_start':CORE,'core_end':implementation_digest(),
        'source_before':before,'source_after':after,'identity_stable':stable,'selection':selection,'actual_module':ark_sim.__file__,
        'explicit_content_inputs':{key:os.environ[key] for key in ('CAMPAIGN_SUMMON_PACKAGE','ARKSIM_M10_REVIEW_ROOT')},'actual_game_accuracy_verified':False,'formal_approved':False}
    (out/'full_suite_20261003.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
