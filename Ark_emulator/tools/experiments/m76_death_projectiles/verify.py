import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m76_death_projectiles_v7_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest


def main():
    import ark_sim,pytest
    core=implementation_digest();assert core==json.loads((ROOT/'validation/campaign/m76_death_projectiles/composition_v7.json').read_bytes())['core']
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    files=[*list((RUNTIME/'ark_sim').rglob('*.py')),RUNTIME/'ark_sim/rules/contracts.json',
        Path(__file__),Path(__file__).with_name('test_death.py'),ROOT/'tools/candidates/m76_death_projectiles/prepare.py',
        ROOT/'tools/candidates/m76_death_projectiles/death_projectiles.py',ROOT/'tools/build_chapter04_bslime_model.py',
        ROOT/'packages/campaign/chapter04_sources/native.reference.json',ROOT/'packages/campaign/chapter04_units/bslime.reference_model.json',ROOT/'tools/campaign_ordered_checkpoint.py']
    def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before=guard();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([str(Path(__file__).with_name('test_death.py')),'-q','--tb=short'],plugins=[Capture()]));after=guard()
    mod=next(m for n,m in sys.modules.items() if n.endswith('test_death'));result={'passed':code==0 and before==after and implementation_digest()==core,
        'core_start':core,'core_end':implementation_digest(),'source_start':before,'source_end':after,'actual_module':ark_sim.__file__,
        'cases':cases,'actual_inputs':mod.INPUTS,'scope':'Author postmortem source consumer; no independent review or whole stage approval','whole_stage_executed':False}
    out=ROOT/'validation/campaign/m76_death_projectiles';(out/'initial_tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
