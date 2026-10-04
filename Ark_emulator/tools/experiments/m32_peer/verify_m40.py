import json,sys,io,contextlib,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m40_typed_board_scope_candidate';sys.path.insert(0,str(RUNTIME));OUT=ROOT/'validation/campaign/m32_peer'
import ark_sim,pytest
from ark_sim import Engine
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest
import test_m40_fields as h
CORE=h.CORE;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return {'path':str(path.relative_to(ROOT)).replace(chr(92),'/'),'sha256':sha(path)}
class Rows:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.rows.append({'case':report.nodeid,'result':report.outcome,'seconds':report.duration})
def main():
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';files=[Path(__file__),Path(__file__).with_name('test_m40_fields.py'),Path(__file__).with_name('static_overrides_m34.py'),RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json'];locks={str(p):sha(p) for p in files};plugin=Rows();buf=io.StringIO();begun=time.time()
 with contextlib.redirect_stdout(buf):code=pytest.main(['tools/experiments/m32_peer/test_m40_fields.py','-q','--tb=short'],plugins=[plugin])
 (OUT/'m40_tests.log').write_text(buf.getvalue(),encoding='utf8');assert code==0;cases=[]
 for name,p,commands,expected in [('entry_exit',h.regen_scene(),[(3,'ability/in'),(33,'ability/out')],50),('halfopen',h.regen_scene(.2),[(3,'ability/in')],41)]:
  s=h.make(p)
  for at,ability in commands:s.submit({'action':'skill','source':'target','ability':ability},at=at)
  s.advance(20 if name=='entry_exit' else 7);cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(15 if name=='entry_exit' else 2);r.advance(15 if name=='entry_exit' else 2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();assert abs(s.ctx.resources.current('target','hp')-expected)<1e-9;cases.append({'case':name,'fixture':save(OUT/(name+'.m40.fixture.json'),p),'commands':save(OUT/(name+'.m40.commands.json'),s.export_replay()),'checkpoint':save(OUT/(name+'.m40.checkpoint.json'),cp),'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'expected_hp':expected,'checkpoint_equal':True,'replay_equal':True})
 assert all(sha(Path(p))==v for p,v in locks.items()) and implementation_digest()==CORE
 old=['static_override_original.json','normal_role_spoof_m36.json','nested_board_m39_failure.json'];report={'schema':'ark-sim/static-field-scope-independent-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,'source_locks_start':locks,'source_locks_end':{p:sha(Path(p)) for p in locks},'tests':plugin.rows,'actual_cases':cases,'historical_failures':[{'path':'validation/campaign/m32_peer/'+n,'sha256':sha(OUT/n)} for n in old],'elapsed_seconds':time.time()-begun,'scope':'generic declared static field role/effective inputs, data-reference scoping and consumer math correctness; native tile callbacks/source profiles remain separately pending','client_verified':False,'formal_approval':False};save(OUT/'m40_final_review.json',report);print(json.dumps({'passed':True,'cases':len(plugin.rows),'core':CORE,'sha256':sha(OUT/'m40_final_review.json')}))
if __name__=='__main__':main()
