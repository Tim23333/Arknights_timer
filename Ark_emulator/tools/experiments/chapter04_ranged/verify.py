import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    expected='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
    assert Path(ark_sim.__file__).resolve().parent==ROOT/'ark_sim' and implementation_digest()==expected
    files=[Path(__file__),Path(__file__).with_name('test_ranged.py'),ROOT/'tools/build_chapter04_ranged_units.py',
        ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'packages/campaign/chapter04_sources/native.reference.json',
        ROOT/'ark_sim/rules/contracts.json',*[ROOT/'packages/campaign/chapter04_units/ranged'/name for name in ('table.reference_model.json','source_circle.reference_model.json')]]
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=int(pytest.main([str(Path(__file__).with_name('test_ranged.py')),'-q','--tb=short'],plugins=[Capture()]))
    after=guard();mod=next(m for name,m in sys.modules.items() if name.endswith('test_ranged'))
    result={'passed':code==0 and before==after and implementation_digest()==expected,'core_start':expected,'core_end':implementation_digest(),
        'source_start':before,'source_end':after,'actual_module':ark_sim.__file__,'cases':cases,'actual_inputs':mod.INPUTS,
        'scope':'Two source-bound ranged units and dcross combat branch; independent peer and whole stage pending','whole_stage_executed':False,'actual_client_verified':False}
    out=ROOT/'validation/campaign/chapter04_ranged';out.mkdir(parents=True,exist_ok=True);(out/'author_tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
