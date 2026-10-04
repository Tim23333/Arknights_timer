import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
CORE='348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),RUNTIME/'ark_sim/rules/contracts.json',Path(__file__),Path(__file__).with_name('test_order.py'),
        ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/m75_packets/verification.json',
        ROOT/'validation/campaign/m73_environment_peer/callback_reproduction/retire_second-fixture.json']
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([str(Path(__file__).with_name('test_order.py')),'-q','--tb=short'],plugins=[Capture()]));after=guard()
    mod=next(m for name,m in sys.modules.items() if name.endswith('test_order'))
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'actual_inputs':mod.INPUTS,'scope':'Fresh independent queued content reactions, rejected in-callback checkpoint and valid idle saved reload; host callback instrumentation scoped; no mid-callback continuation or fullstage approval'}
    out=ROOT/'validation/campaign/m75_root_peer';out.mkdir(parents=True,exist_ok=True);(out/'initial_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
