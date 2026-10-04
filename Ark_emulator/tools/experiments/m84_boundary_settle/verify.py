import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m84_boundary_settle_v2_candidate'
CORE=__import__('json').loads((ROOT/'validation/campaign/m84_boundary_settle/composition.json').read_bytes())['core']
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),*list((RUNTIME/'ark_sim').rglob('*.json')),Path(__file__),Path(__file__).with_name('test_live.py'),
        ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/m70_applicability_v2/candidate_final.json']
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([str(Path(__file__).with_name('test_live.py')),'-q','--tb=short'],plugins=[Capture()]));after=guard()
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'cases':cases,'scope':'Fresh independent mixed contributions, flag-vs-combo immunity, half-open expiry and readonly getters; directhostCP only no commandreplay claim'}
    out=ROOT/'validation/campaign/m84_boundary_settle';out.mkdir(parents=True,exist_ok=True);(out/'initial_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
