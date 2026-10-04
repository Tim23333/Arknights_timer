import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m67_connectivity_snapshot_candidate'
CORE='138cf9a4927f20162b207d07cb34441a41aabe887e0a06630fcd36cef9a6a07b'
OUT=ROOT/'validation/campaign/m67_connectivity';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest


def main():
    import ark_sim,pytest
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    guards=[Path(__file__),Path(__file__).with_name('test_connectivity.py'),ROOT/'tools/candidates/m67_connectivity_source_snapshot/prepare.py',RUNTIME/'ark_sim/domains/deploy_connectivity.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=pytest.main([str(Path(__file__).with_name('test_connectivity.py')),'-q','--tb=short'],plugins=[Capture()])
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    module=next(m for name,m in sys.modules.items() if name.endswith('test_connectivity'))
    report={'schema':'ark-sim/connectivity-model-tests/v1','passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'actual_inputs':module.INPUTS,'exit_code':int(code),'whole_stage_executed':False,'actual_client_verified':False}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'initial_tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
