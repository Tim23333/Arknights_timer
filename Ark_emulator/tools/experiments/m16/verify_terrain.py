"""Coherent source/runtime-guarded tests and event witnesses, no receipt."""
import hashlib
import json
from pathlib import Path
import sys
import difflib
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=ROOT.parent/'unpack_work/campaign_m16_terrain_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m15_category_candidate'
sys.path.insert(0,str(CANDIDATE))
import ark_sim
assert Path(ark_sim.__file__).resolve().parent==CANDIDATE/'ark_sim'
sys.path.append(str(ROOT))
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
import pytest
from tools.experiments.m16 import test_terrain as t
from tools.build_chapter01_emp_terrain import build,OUTPUT,SOURCE
from tools.experiments.m15_peer import verify as h
CORE=implementation_digest()
OUT=ROOT/'validation/campaign/m16_terrain'
OUT.mkdir(parents=True,exist_ok=True)
FILES=[Path(__file__),Path(t.__file__),Path(h.__file__),ROOT/'tools/build_chapter01_emp_terrain.py',OUTPUT,SOURCE,
       CANDIDATE/'ark_sim/rules/contracts.json',CANDIDATE/'ark_sim/content/presets/ark_standard.json']
n=json.loads(SOURCE.read_bytes())
FILES.extend(ROOT.parent/x['source']['path'] for x in (n['prefab'],n['skill_prefab']))
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
start=hashes();assert json.loads(OUTPUT.read_bytes())==build()
cases=[]
class Capture:
    previous=None
    def pytest_runtest_setup(self,item):self.previous=h.LAST
    def pytest_runtest_makereport(self,item,call):
        if call.when!='call':return
        c={'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed'}
        if call.excinfo is not None:c['error']=str(call.excinfo.value)
        if h.LAST is not self.previous and h.LAST is not None:
            s=h.LAST;c['fixture']={'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,
             'initial_scenario':thaw(s.program.scenario),'commands':s.export_replay(),
             'world':s.snapshot(),'events':[thaw(e) for e in s.session.events if e['type'].startswith(('terrain.','movement.terrain','command.','entity.','damage.','ability.'))]}
            c['all_events_sha256']=digest([thaw(e) for e in s.session.events])
        cases.append(c)
exit_code=pytest.main(['-q',str(Path(t.__file__))],plugins=[Capture()])
regressions=[]
for name,fn in h.CASES.items():
    if name=='source_contract':continue
    try:regressions.append({'name':name,'result':'passed','actual':fn()})
    except Exception as e:regressions.append({'name':name,'result':'failed','error':repr(e)})
end=hashes();stable=start==end and implementation_digest()==CORE
passed=exit_code==0 and stable and all(x['result']=='passed' for x in regressions)
value={'schema':'ark-sim/owned-terrain-candidate-evidence/v1','passed':passed,'formal_approval':False,'review_receipt':False,
 'runtime_module':ark_sim.__file__,'implementation_sha256':CORE,'source_at_start':start,'source_at_completion':end,'identity_stable':stable,
 'cases':cases,'unchanged_EMP_skill_regressions':regressions,
 'tests':[{'path':str(Path(t.__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':start[str(Path(t.__file__))],
           'result':'passed' if exit_code==0 else 'failed'}],
 'scope':'Owned tile World layers, pure rule getters, deployment/path costs, cache invalidation, lifecycle cleanup, rollback and recorded-command CP/replay. No 3D/native comparator/card lifecycle/full EMP/full chapter approval.'}
(OUT/'candidate_final.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
changed=[];patch=[]
for p in sorted((CANDIDATE/'ark_sim').rglob('*')):
    if not p.is_file() or p.suffix not in ('.py','.json'):continue
    rel=p.relative_to(CANDIDATE);old=BASE/rel
    if old.exists() and old.read_bytes()==p.read_bytes():continue
    changed.append({'path':str(rel).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    patch.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf8').splitlines(True),
      fromfile='a/'+str(rel).replace('\\','/'),tofile='b/'+str(rel).replace('\\','/')))
(OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8',newline='')
(OUT/'changed_files.json').write_text(json.dumps({'core':CORE,'files':changed},indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':passed,'core':CORE,'new_tests':len(cases),'EMP_regressions':[(x['name'],x['result']) for x in regressions],
                  'input_sha256':start[str(OUTPUT)]}))
raise SystemExit(0 if passed else 1)
