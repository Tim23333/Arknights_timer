"""Bound author execution and immutable v2 delivery; v1 evidence stays intact."""
import hashlib,json,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
CANDIDATE=ROOT.parent/'unpack_work/campaign_elemental_v2_candidate'
CORE='4ef70d6fb24ecf9819b12d97bc1893005e274278b9a1798ba265ed833bfa0add'
REPORT=ROOT/'validation/campaign/chapter09_elemental_v2'
RUN=Path('E:/ArkSimLogs/runs/chapter09_elemental_final_v2')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def guards(root):return {p.relative_to(root).as_posix():sha(p) for p in (root/'ark_sim').rglob('*') if p.suffix in ('.py','.json')}
def write(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    RUN.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(CANDIDATE));sys.path.insert(1,str(ROOT))
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==CORE
    oldfreeze=json.loads((ROOT/'validation/campaign/chapter09_elemental_v1/freeze.json').read_bytes())
    oldroot=ROOT.parent/'unpack_work/campaign_elemental_v1_candidate'
    assert guards(oldroot)==oldfreeze['guards']
    before=guards(CANDIDATE);primary=guards(ROOT)
    shutil.copyfile(oldroot/'ark_emulator/levels/packs/level_main_00-01.json',CANDIDATE/'level_main_00-01.reference.json')
    level=CANDIDATE/'ark_emulator/levels/packs/level_main_00-01.json';level.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(oldroot/'ark_emulator/levels/packs/level_main_00-01.json',level)
    import pytest
    cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,'failure':str(report.longrepr) if report.failed else None})
    started=time.monotonic()
    code=int(pytest.main([str(HERE/'test_author_v2.py'),str(HERE/'catalog_v1.py'),
        str(ROOT/'tests_v2/test_abilities.py')+'::test_hp_sacrifice_cost_immediately_checks_real_lifecycle_and_interrupts_cast',
        '-q','--basetemp',str(RUN/'temp'),'-o','cache_dir='+str(RUN/'cache')],plugins=[Capture()]))
    assert code==0 and len(cases)==31 and before==guards(CANDIDATE) and primary==guards(ROOT)
    design=json.loads((ROOT/'validation/campaign/chapter09_elemental_v1/design.v1.json').read_bytes())
    design['core']=CORE;design['new_v2_changes']=['Optional lifecycle hook preserves old direct RuntimeContext callers.','Scenario-only elemental component overrides install real expiry handler and validate effective complete profile/calculation contracts before execution.']
    write(REPORT/'design.json',design)
    write(REPORT/'author.final.json',{'core':CORE,'passed':True,'cases':cases,'count':len(cases),'seconds':time.monotonic()-started,
        'guards_start':before,'guards_end':guards(CANDIDATE),'primary_guards':primary,'old_v1_guards_stable':True,
        'scope':'Generic mechanism author only, no native stage/NoSource/ELEMENT pipeline admission.'})
    write(REPORT/'freeze.json',{'core':CORE,'candidate':str(CANDIDATE),'parent_core':'82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae',
        'relative_frozen_v1_delta':[key for key in before if before[key]!=oldfreeze['guards'][key]],
        'guards':before,'helpers':{str(p):sha(p) for p in HERE.rglob('*') if p.suffix in ('.py','.json')},
        'receipts':{str(p):sha(p) for p in [REPORT/'author.final.json',REPORT/'design.json']},
        'author_gate':True,'full_gate':False,'baseline_gate':False,'independent_gate':False,'primary_modified':False})
    print(json.dumps({'core':CORE,'freeze_sha':sha(REPORT/'freeze.json'),'author_sha':sha(REPORT/'author.final.json'),'cases':31}),flush=True)

if __name__=='__main__':main()
