import hashlib,json,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def main():
    import pytest
    files=[Path(__file__),Path(__file__).with_name('test_cli.py'),ROOT/'tools/run_campaign_disk_runthrough_v15.py',
        ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py',ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v13.py',
        ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py',ROOT/'tools/campaign_ordered_checkpoint.py']
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();out=ROOT/'validation/campaign/disk_runthrough_v15';tmp=out/('cases-'+uuid.uuid4().hex);cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=int(pytest.main([str(Path(__file__).with_name('test_cli.py')),'-q','--basetemp',str(tmp),'--tb=short'],plugins=[Capture()]))
    after=guard();report={'passed':code==0 and before==after,'source_start':before,'source_end':after,'cases':cases,'actual_casefiles':str(tmp),
        'file_sha256':{str(p.relative_to(tmp)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp.rglob('*') if p.is_file()},
        'scope':'Actual tiny CLI full lifecycle/referenceCP/replay, preserved post-terminal command, wronghelperSHA and forbidden fullhistory reads; no M77 protocol/longstage approval'}
    (out/'cli_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
