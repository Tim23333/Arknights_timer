"""Guard actual M76 source-consumer and compatible tests before freezing."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate'
CORE='67028cc91fe55931a62c19d29c8a04dcc4bc6c354b059b1acaac1982733147ad'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json')),
        *list((ROOT/'tools/candidates/m76_death_projectiles').glob('*.py')),*list(Path(__file__).parent.glob('*.py')),
        ROOT/'tools/build_chapter04_bslime_model.py',ROOT/'tools/campaign_ordered_checkpoint.py',
        ROOT/'packages/campaign/chapter04_units/bslime.reference_model.json',ROOT/'packages/campaign/chapter04_sources/native.reference.json']
    selection=[str(Path(__file__).with_name('test_death.py')),'tests_v2/test_engine.py','tests_v2/test_damage_hooks_random.py',
        'tests_v2/test_event_resources.py','tests_v2/test_replay.py','tools/experiments/m38/test_refs.py','tools/experiments/m38/test_storage.py']
    files.extend(ROOT/p for p in selection[1:])
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome})
    code=int(pytest.main([*selection,'-q','--tb=short'],plugins=[Capture()]))
    comparison=subprocess.run([sys.executable,str(Path(__file__).with_name('compare_parent.py'))],cwd=ROOT,capture_output=True,text=True)
    after=guard();out=ROOT/'validation/campaign/m76_death_projectiles'
    reports={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('initial_tests.json','no_profile_comparison.json')}
    result={'passed':code==0 and comparison.returncode==0 and before==after and implementation_digest()==CORE,
        'core_start':CORE,'core_end':implementation_digest(),'source_start':before,'source_end':after,'selection':selection,'cases':cases,
        'comparison_exit':comparison.returncode,'comparison_output':comparison.stdout+comparison.stderr,'proof_sha256':reports,
        'source_model_sha256':hashlib.sha256((ROOT/'packages/campaign/chapter04_units/bslime.reference_model.json').read_bytes()).hexdigest(),
        'scope':'Author frozen source consumer, 13 boundaries and 109 compatibility plus exact no-opt values; independent peer required',
        'whole_stage_executed':False,'actual_client_verified':False}
    path=out/'candidate_final.json';assert not path.exists();path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':result['passed'],'cases':len(cases),'core':CORE,'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
