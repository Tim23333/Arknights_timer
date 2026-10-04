"""Freeze candidate and author receipts before admitting the full-suite run."""
import hashlib,json,shutil,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
CANDIDATE=ROOT.parent/'unpack_work/campaign_elemental_v1_candidate'
EXPECTED='838ce3cc2cb019f91f594b7a40ac999a1300b8088f4603418a3029b253186cb2'
PARENT='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'
REPORT=ROOT/'validation/campaign/chapter09_elemental_v1'
RUN=Path('E:/ArkSimLogs/runs/chapter09_elemental_final_v1')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guards(root):return {p.relative_to(root).as_posix():sha(p) for p in (root/'ark_sim').rglob('*') if p.suffix in ('.py','.json')}
def write(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    RUN.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(CANDIDATE));sys.path.insert(1,str(ROOT))
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==EXPECTED
    parent=json.loads((ROOT/'ark_sim/rules/contracts.json').read_bytes())
    current=json.loads((CANDIDATE/'ark_sim/rules/contracts.json').read_bytes())
    assert current['contracts'][:99]==parent['contracts'] and len(parent['contracts'])==99
    shutil.copyfile(ROOT/'ark_sim/rules/contracts.json',HERE/'contracts.parent99.json')
    write(HERE/'contracts.elemental6.json',current['contracts'][99:])
    write(HERE/'catalog.locks.json',{'parent_sha256':sha(HERE/'contracts.parent99.json'),'elemental_sha256':sha(HERE/'contracts.elemental6.json')})
    # New runner uses the previous full-suite orchestration unchanged except for
    # one exact old-count expectation replacement and isolated log paths.
    runner=(ROOT/'tools/chapter08_joint_v2/run_full_suite_v2.py').read_text(encoding='utf-8')
    runner=runner.replace('from tools.chapter08_joint_v2.test_catalog_v1 import (\n        test_catalog_is_exact_previous98_plus_dynamic_lifetime_and_readonly as replacement)',
                          'from tools.chapter09_elemental.catalog_v1 import (\n        test_catalog_is_exact_previous99_plus_elemental6_and_readonly as replacement)')
    runner=runner.replace("ROOT / 'tools/chapter08_joint_v2/catalog_v1.py'","ROOT / 'tools/chapter09_elemental/catalog_v1.py'")
    runner=runner.replace("ROOT / 'tools/chapter08_joint_v2/test_catalog_v1.py'","ROOT / 'tools/chapter09_elemental/catalog.locks.json'")
    runner=runner.replace("ROOT / 'tools/candidates/chapter08_joint_v2/base_contracts.json'","ROOT / 'tools/chapter09_elemental/contracts.parent99.json', ROOT / 'tools/chapter09_elemental/contracts.elemental6.json'")
    runner=runner.replace("pytest.main(['tests_v2', '-q', '--tb=short']", "pytest.main(['tests_v2', '-q', '--tb=short', '--basetemp', str(Path('E:/ArkSimLogs/runs/chapter09_elemental_full_v1/temp')), '-o', 'cache_dir=E:/ArkSimLogs/runs/chapter09_elemental_full_v1/cache']")
    runner=runner.replace('New lifetime contract extends exact prior98 catalog; no original definition changed','Six elemental contracts extend exact prior99 catalog; no original definition changed')
    runner_path=HERE/'run_full_suite_v1.py';assert not runner_path.exists();runner_path.write_text(runner,encoding='utf-8')
    oldlevel=ROOT/'ark_emulator/levels/packs/level_main_00-01.json';target=CANDIDATE/'ark_emulator/levels/packs/level_main_00-01.json'
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(oldlevel,target)
    before=guards(CANDIDATE);primary_before=guards(ROOT);cases=[]
    import pytest
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'nodeid':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
    started=time.monotonic()
    code=int(pytest.main([str(HERE/'test_author_v1.py'),str(HERE/'catalog_v1.py'),'-q','--basetemp',str(RUN/'temp'),'-o','cache_dir='+str(RUN/'cache')],plugins=[Capture()]))
    assert code==0 and len(cases)==28 and all(x['outcome']=='passed' for x in cases)
    assert guards(CANDIDATE)==before and guards(ROOT)==primary_before
    write(REPORT/'author.final.json',{'passed':True,'core':EXPECTED,'scope':'Generic elemental mechanism author tests, not native unit/stage acceptance.',
         'cases':cases,'case_count':len(cases),'seconds':time.monotonic()-started,'guards_start':before,'guards_end':guards(CANDIDATE),
         'primary_guards':primary_before,'primary_unchanged':True,'client_verified':False})
    write(REPORT/'design.v1.json',{'schema':'ark-sim/elemental-generic-design/v1','parent_core':PARENT,'core':EXPECTED,
         'component':'Finite content-defined elements, explicit four rules per element plus eligibility rule; capacities/resistance/recovery/durations remain content values.',
         'contracts':[x['id'] for x in current['contracts'][99:]],
         'operations':['elemental_damage (one raw amount or pure packet rule)','elemental_attack (atomic actor health effect, then independently calculated elemental effect)'],
         'timing':'Recovery samples current phase0 effective attributes for elapsed prior logical interval. Break expiry is a real finite task; owned generation, task identity/sequence, due, phase and target lifecycle stamp all match.',
         'provenance':'First crossing packet captures original source ID, runtime death/lifecycle generations, state and immutable launch-time entity snapshot; later source retirement does not change the cause.',
         'callbacks':'Target owns declared finite on_break/on_end effects. Re-read target lifecycle and break generation between callbacks; a new break aborts old on_end remainder. This is not permission for a dead actor to cast.',
         'failure':'Callback calculation/effect failures propagate. Their atomic domain writes/events/RNG/scheduled work roll back. Session retains its standard dispatched-task consumption and failure record; this candidate does not change kernel failure recovery.',
         'numeric_policy':'No game-specific capacities, percentages, damage amounts or element IDs in domain. Nonnegative loss and positive capacity/duration are protocol bounds; resistance and rates are merely finite and formulas/clamps are replaceable.',
         'not_implemented':['NoSource NORMAL ARTS/physical expansion (Root separate candidate)','ELEMENT health damage pipeline','Native Duspfr deathlike continuation','Pillar terrain/collapse mechanics'],
         'source_plan_freeze':'packages/campaign/chapter09_source_prepare/source.freeze.v2.json'})
    before_parent=guards(ROOT);delta=[p for p in before_parent if before_parent[p]!=before[p]]
    write(REPORT/'freeze.json',{'candidate':str(CANDIDATE),'core':EXPECTED,'parent_core':PARENT,
         'guards':before,'changed':delta,'added':sorted(set(before)-set(before_parent)),
         'helpers':{str(p):sha(p) for p in HERE.glob('*') if p.suffix in ('.py','.json')},
         'receipts':{str(p):sha(p) for p in [REPORT/'author.final.json',REPORT/'design.v1.json']},
         'author_gate':True,'independent_gate':False,'full_gate':False,'baseline_gate':False,'primary_modified':False})
    print(json.dumps({'freeze_sha':sha(REPORT/'freeze.json'),'author_sha':sha(REPORT/'author.final.json'),'cases':len(cases),'core':EXPECTED}),flush=True)

if __name__=='__main__':main()
