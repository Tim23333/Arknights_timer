import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m74_death_claim_candidate'
CORE='74ac865eb120c0fd180e096d1e2cc2928d35c7fa0d981e62e77f1e0dafdd90e7'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),RUNTIME/'ark_sim/rules/contracts.json',Path(__file__),
        Path(__file__).with_name('test_rebirth.py'),ROOT/'tools/experiments/m61_roster_peer/test_revised.py',
        ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'validation/campaign/m74_death_claim/candidate_final.json']
    def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=hashes();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([str(Path(__file__).with_name('test_rebirth.py')),'-q','--tb=short'],plugins=[Capture()]));after=hashes()
    module=next(m for name,m in sys.modules.items() if name.endswith('test_rebirth'))
    result={'passed':code==0 and before==after and implementation_digest()==CORE,'core_start':CORE,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'actual_module':ark_sim.__file__,'cases':cases,'actual_inputs':module.INPUTS,'fixtures':module.CAPTURES,
        'scope':'Unchanged independent rebirth peer expectations including original true duplicate-kill failure; no wholeFrost or no-source integration approval'}
    out=ROOT/'validation/campaign/m74_root_peer';out.mkdir(parents=True,exist_ok=True);(out/'final_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
