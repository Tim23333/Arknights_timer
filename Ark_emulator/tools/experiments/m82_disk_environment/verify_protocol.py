import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m82_disk_environment_candidate'
CORE='65134744f50a9a1641f339965a8f4925927e5de51aedff9a39eea0550e887522'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json')),Path(__file__),Path(__file__).with_name('test_protocol.py'),
        ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py',ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v13.py',
        ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py',ROOT/'tools/campaign_ordered_checkpoint.py']
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([str(Path(__file__).with_name('test_protocol.py')),'-q','--tb=short'],plugins=[Capture()]));after=guard()
    report={'passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'scope':'Independent actual-byte, serialization order and concurrent observation protocol; no long-stage/RSS acceptance'}
    out=ROOT/'validation/campaign/m82_disk_environment';out.mkdir(parents=True,exist_ok=True);(out/'initial_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
