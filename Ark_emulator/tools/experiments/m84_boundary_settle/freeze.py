import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m84_boundary_settle_v2_candidate'
CORE='e8fe0c931358f6f09e6e209ff70948dd1d17fb80aeae969afd71d2c8ab1bef3e'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    selection=[str(Path(__file__).parent),'tests_v2/test_kernel.py','tests_v2/test_replay.py','tests_v2/test_buff_mode_lifecycle.py','tests_v2/test_auras.py']
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json')),*list(Path(__file__).parent.glob('*.py')),
        ROOT/'tools/candidates/m84_boundary_settle/prepare.py',ROOT/'tools/campaign_ordered_checkpoint.py',
        ROOT/'packages/campaign/chapter04_boss/m70/immunity.reference_model.json',RUNTIME/'ark_emulator/levels/packs/level_main_00-01.json']
    files.extend(ROOT/p for p in selection[1:])
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=int(pytest.main([*selection,'-q','--tb=short'],plugins=[Capture()]));after=guard()
    out=ROOT/'validation/campaign/m84_boundary_settle';checks={}
    for name in ('no_profile_comparison.json','reconstruction.json'):
        checks[name]=hashlib.sha256((out/name).read_bytes()).hexdigest()
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'selection':selection,'other_proof_sha256':checks,
        'scope':'Clockboundary/cache-coherence author revision; old independent 3 expectations now pass, plus publicCP/replay/kernel and source/compatibility; new peer required','whole_stage_executed':False}
    path=out/'candidate_final.json';assert not path.exists();path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':result['passed'],'cases':len(cases),'core':CORE,'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
