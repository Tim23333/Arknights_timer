"""Guarded compatibility on the new composition; no prior proof migration."""
import hashlib,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT));sys.path.insert(2,str(ROOT/'tests_v2'))
os.environ['ARKSIM_M10_REVIEW_ROOT']=str(RUNTIME)
os.environ['CAMPAIGN_SUMMON_PACKAGE']=str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')
from ark_sim.adapters.api import implementation_digest
import pytest
CORE='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert implementation_digest()==CORE
    selection=[ROOT/'tests_v2'/n for n in ['test_abilities.py','test_activation_controls.py','test_temporal_and_recovery_gate.py','test_damage_hooks_random.py','test_buff_mode_lifecycle.py','test_scenario_effects.py','test_m8_timeline.py']]
    paths=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'}]+selection+[Path(__file__)]
    before={str(p):sha(p) for p in paths};cases=[];start=time.monotonic()
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
    code=int(pytest.main([*[str(p) for p in selection],'-q','--tb=short'],plugins=[Capture()]))
    assert before=={str(p):sha(p) for p in paths} and implementation_digest()==CORE
    out=ROOT/'validation/campaign/chapter06_buff_join_v9/focused_v9.json'
    with out.open('x',encoding='utf8') as f:json.dump({'core':CORE,'actual_exit':code,'cases':cases,'source_guards':before,'elapsed_seconds':time.monotonic()-start,'scope':'Selected existing compatibility; combined independent source/complete suite pending'},f,indent=2)
    print(json.dumps({'exit':code,'cases':len(cases),'sha':sha(out)}));raise SystemExit(code)


if __name__=='__main__':main()
