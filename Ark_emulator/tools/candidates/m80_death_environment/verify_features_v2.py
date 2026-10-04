import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m80_death_environment_candidate'
CORE='1dad89a7eabf04a0bf0633bacc14ad303a2d59196689af1e24d0858de4df36a2'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    selection=['tools/experiments/m80_death_environment','tests_v2/test_engine.py','tests_v2/test_damage_hooks_random.py',
        'tests_v2/test_event_resources.py','tests_v2/test_replay.py','tests_v2/test_scenario_effects.py','tests_v2/test_qualified_area_visibility_integration.py']
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json')),Path(__file__),Path(__file__).with_name('prepare.py'),
        ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/build_chapter04_bslime_model.py',ROOT/'packages/campaign/chapter04_units/bslime.reference_model.json',ROOT/'validation/campaign/m76_death_projectiles/candidate_final.json',ROOT/'validation/campaign/m75_packets/verification.json',ROOT/'validation/campaign/m74_death_claim/candidate_final.json',
        ROOT/'packages/campaign/chapter04_environment/source.reference.json',ROOT/'packages/campaign/chapter04_environment/volcano.reference_module.json',
        ROOT/'packages/campaign/chapter04_plans/source.plan.json']
    for entry in selection:
        path=ROOT/entry;files.extend(path.rglob('*.py') if path.is_dir() else [path])
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=int(pytest.main([*selection,'-q','--tb=short'],plugins=[Capture()]));after=guard()
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'selection':selection,'actual_module':ark_sim.__file__,
        'scope':'Combined source damage/rebirth/death claim/field ordering features; baseline/fullsuite/whole4-9 separate'}
    out=ROOT/'validation/campaign/m80_death_environment/guarded_features_v2.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
