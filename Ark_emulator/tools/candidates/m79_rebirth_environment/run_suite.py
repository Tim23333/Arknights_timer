"""Run complete selected V2 regression through frozen M79 and actual catalog94."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m79_rebirth_environment_candidate'
CORE='2e734d6a58b825cecfd85966d49a62de33281131c78b59c3764ba296a7466ef3'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.rules.catalog import load_catalog
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    assert len(load_catalog()['contracts'])==94
    os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
    os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
    source=ROOT/'tests_v2/test_rules.py';dest=ROOT/'tools/experiments/m79_rebirth_environment/test_rules_catalog.py'
    raw=source.read_bytes();assert raw.count(b'len(DEFAULT_CATALOG["contracts"]) == 92')==1
    clone=raw.replace(b'len(DEFAULT_CATALOG["contracts"]) == 92',b'len(DEFAULT_CATALOG["contracts"]) == 94').replace(b'test_catalog_has_92_contracts',b'test_catalog_has_94_contracts')
    clone=clone.replace(b'Path(__file__).parents[1] / "docs/v2_examples/custom_guard.json"',b'Path(__file__).parents[3] / "docs/v2_examples/custom_guard.json"')
    dest.write_bytes(clone)
    selection=['tests_v2','--ignore=tests_v2/test_rules.py',
        *['tools/experiments/m38/'+name for name in ('test_storage.py','test_refs.py','test_fields.py','test_static_owner.py','test_overrides.py','test_board_scope.py','test_role.py')],
        'tools/experiments/m68_integration','--ignore=tools/experiments/m68_integration/test_rules_catalog.py',
        'tools/experiments/m79_rebirth_environment','tools/experiments/m26_content/test_composition.py','tools/experiments/m23','tools/experiments/chapter02_tiles']
    paths=[*list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json')),Path(__file__),source,dest,
        Path(os.environ['CAMPAIGN_SUMMON_PACKAGE']),RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json']
    for name in selection:
        if name.startswith('--'):continue
        path=ROOT/name;paths.extend(path.rglob('*.py') if path.is_dir() else [path])
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=guard();print(json.dumps({'core':CORE,'actual_module':ark_sim.__file__,'catalog_count':94,'source_files':len(before)}),flush=True)
    code=int(pytest.main([*selection,'-q','--tb=short']));after=guard()
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'exit_code':code,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'selection':selection,'actual_module':ark_sim.__file__,'catalog_count':94,
        'copied_catalog_test_changes':['count/name92->94','same fixture absolute location via parents3'],'actual_client_verified':False}
    out=ROOT/'validation/campaign/m79_rebirth_environment/full_suite.json';out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
