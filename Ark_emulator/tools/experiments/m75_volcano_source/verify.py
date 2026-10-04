"""Guard actual source-field composition, keeping it separate from full 4-9."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
CORE='348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))


def main():
    import ark_sim,pytest
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    guards=list((RUNTIME/'ark_sim').rglob('*.py'))+[RUNTIME/'ark_sim/rules/contracts.json',
        ROOT/'tools/build_chapter04_volcano_module.py',ROOT/'tools/build_reference_stage_scenario_v2.py',
        ROOT/'tools/campaign_ordered_checkpoint.py',Path(__file__),Path(__file__).with_name('test_volcano_source.py'),
        ROOT/'packages/campaign/chapter04_environment/source.reference.json',
        ROOT/'packages/campaign/chapter04_environment/volcano.reference_module.json',
        ROOT/'packages/campaign/chapter04_plans/source.plan.json']
    def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards}
    before=hashes();cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=int(pytest.main([str(Path(__file__).with_name('test_volcano_source.py')),'-q','--tb=short'],plugins=[Capture()]))
    after=hashes();module=next(m for name,m in sys.modules.items() if name.endswith('test_volcano_source'))
    result={'passed':code==0 and before==after and implementation_digest()==CORE,
        'core_start':CORE,'core_end':implementation_digest(),'source_before':before,'source_after':after,
        'actual_module':ark_sim.__file__,'cases':cases,'actual_inputs':module.INPUTS,
        'scope':'Actual eight 4-9 source cells, typed 700 PURE, 13+6u clock, ordered disk reload and replay; no native enemies/timeline',
        'callback_chain_verified':False,'whole_stage_executed':False,'actual_client_verified':False}
    out=ROOT/'validation/campaign/m75_volcano_source';out.mkdir(parents=True,exist_ok=True)
    (out/'volcano_source_tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
