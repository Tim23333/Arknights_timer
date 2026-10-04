"""Read-only peer report with full source/catalog/tool before/end guards."""
from pathlib import Path
import hashlib,json,sys

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m73_environment_integrated_v2_candidate'
OUT=ROOT/'validation/campaign/m73_environment_peer'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guards():
    result={'runtime_python':{str(p.relative_to(RUNTIME/'ark_sim')):sha(p) for p in sorted((RUNTIME/'ark_sim').rglob('*.py'))},
        'runtime_catalog':{str(p.relative_to(RUNTIME/'ark_sim')):sha(p) for p in sorted((RUNTIME/'ark_sim').rglob('*.json'))}}
    paths=[ROOT/'tools/candidates/m73_environment_integration/prepare.py',ROOT/'tools/experiments/m73_environment/test_fields.py',
        ROOT/'tools/experiments/m73_environment/verify.py',Path(__file__),Path(__file__).with_name('test_peer.py'),
        ROOT/'packages/campaign/chapter04_environment/source.reference.json',ROOT/'tools/campaign_ordered_checkpoint.py']
    result['tools_and_source']={str(p):sha(p) for p in paths}
    return result


def main():
    import pytest
    assert implementation_digest()=='1b548c29fba3dd19c177fbb458a0226e496b15a03c5c2a3599243bcb20e40932'
    before=guards();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'longrepr':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([str(Path(__file__).with_name('test_peer.py')),'-q','--tb=short'],plugins=[Capture()]))
    after=guards();assert before==after and implementation_digest()=='1b548c29fba3dd19c177fbb458a0226e496b15a03c5c2a3599243bcb20e40932'
    report={'core':implementation_digest(),'passed':code==0,'exit_code':code,'start':before,'end':after,'guards_equal':True,'cases':cases,
        'scope':'Fresh peer small cases; legal queued damage-callback packet boundary included; not fullstage/4-9 evidence'}
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'peer_v2.json').open('x',encoding='utf8') as file:json.dump(report,file,ensure_ascii=False,indent=2);file.write('\n')
    print(json.dumps({'passed':report['passed'],'core':report['core'],'cases':len(cases),'failed':[case['case'] for case in cases if case['outcome']=='failed']}))

if __name__=='__main__':main()
