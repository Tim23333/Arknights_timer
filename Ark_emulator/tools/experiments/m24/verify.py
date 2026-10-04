"""Fresh source/runtime-guarded model evidence; native permission pending."""
import sys,json,hashlib,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m24_enemy_fsm_candidate';BASE=ROOT.parent/'unpack_work/campaign_m23_roster_candidate'
sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
sys.path.append(str(ROOT))
import pytest
from tools.experiments.m24 import test_decisions as t,test_native_profiles as n
from tools.build_enemy_fsm_profiles import build,OUT as PACKAGES
OUT=ROOT/'validation/campaign/m24';OUT.mkdir(parents=True,exist_ok=True)
files=[Path(__file__),Path(t.__file__),Path(n.__file__),ROOT/'tools/build_enemy_fsm_profiles.py',ROOT/'tools/audit_enemy_fsm_source.py',
 ROOT/'packages/campaign/chapter01_behavior/source.reference.json',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json']
for stage in ('01-11','01-12'):
 p=PACKAGES/f'level_main_{stage}.decision.partial.json';assert json.loads(p.read_bytes())==build(stage);files.append(p)
source=json.loads(files[5].read_bytes());files.extend(Path(p) for p in source['source_locks'])
def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
start=hashes();core=implementation_digest();inputs=[];cases=[];current='initial';BaseCompiler=Compiler
class InputCompiler(BaseCompiler):
 def compile(self,data,*args,**kwargs):
  path=OUT/'fixtures'/f'{len(inputs)+1:02d}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((json.dumps(data,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode())
  raw=path.read_bytes();inputs.append({'case':current,'path':str(path),'sha256_before_decode':hashlib.sha256(raw).hexdigest()})
  return super().compile(json.loads(raw),*args,**kwargs)
t.Compiler=InputCompiler;n.Compiler=InputCompiler;ark_sim.Compiler=InputCompiler
base_create=Engine.create;last=None
def actual_create(*args,**kwargs):
 global last
 last=base_create(*args,**kwargs);return last
Engine.create=staticmethod(actual_create)
class Capture:
 def pytest_runtest_setup(self,item):
  global current,last
  current=item.nodeid;last=None
 def pytest_runtest_makereport(self,item,call):
  if call.when=='call':
   c={'nodeid':item.nodeid,'result':'passed' if call.excinfo is None else 'failed','error':str(call.excinfo.value) if call.excinfo else None}
   if last is not None:c.update({'program':last.program.fingerprint,'runtime':last.runtime_fingerprint,'commands':last.export_replay(),'snapshot':last.snapshot(),
    'events':[thaw(e) for e in last.session.events if e['type'] in ('ability.started','damage.accepted','movement.traveled','command.accepted','command.rejected','blocking.changed')]})
   cases.append(c)
code=pytest.main(['-q',str(Path(t.__file__)),str(Path(n.__file__))],plugins=[Capture()]);end=hashes();stable=start==end and core==implementation_digest() and all(hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256_before_decode'] for x in inputs)
value={'schema':'ark-sim/declared-enemy-decision-candidate/v1','passed':code==0 and stable,'identity_stable':stable,'core_start':core,'core_end':implementation_digest(),
 'runtime_module':ark_sim.__file__,'source_start':start,'source_end':end,'fixture_inputs':inputs,'cases':cases,
 'native_actual_correct':False,'formal_approval':False,'review_receipt':False,'scope':'20 model/CP/replay checks; native FSM/target permission/comparator/body still pending'}
(OUT/'candidate_final.json').write_bytes((json.dumps(value,indent=2)+'\n').encode());patch=[];changes=[]
for p in sorted((RUNTIME/'ark_sim').rglob('*')):
 if not p.is_file() or p.suffix not in ('.py','.json'):continue
 rel=p.relative_to(RUNTIME);old=BASE/rel
 if old.exists() and old.read_bytes()==p.read_bytes():continue
 changes.append({'path':rel.as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 patch.extend(difflib.unified_diff(old.read_text().splitlines(True) if old.exists() else [],p.read_text().splitlines(True),fromfile='a/'+rel.as_posix(),tofile='b/'+rel.as_posix()))
(OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8',newline='');(OUT/'changed_files.json').write_text(json.dumps(changes,indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':value['passed'],'core':core,'tests':len(cases),'inputs':len(inputs),'native_actual_correct':False}))
raise SystemExit(0 if value['passed'] else 1)
