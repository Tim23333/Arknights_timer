import sys,json,hashlib,io,contextlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m24_enemy_fsm_candidate';sys.path.insert(0,str(RUNTIME));OUT=ROOT/'validation/campaign/m24_peer';OUT.mkdir(parents=True,exist_ok=True)
import ark_sim,pytest,UnityPy
from ark_sim.adapters.api import implementation_digest
from ark_sim import Engine,Compiler
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
import test_independent as h
CORE=h.CORE;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return {'path':str(path.relative_to(ROOT)).replace(chr(92),'/'),'sha256':sha(path)}
class Rows:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  r=report
  if r.when=='call' or r.failed:self.rows.append({'case':r.nodeid,'result':r.outcome,'seconds':r.duration})
def main():
 assert implementation_digest()==CORE;assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';start=time.time();source=ROOT/'packages/campaign/chapter01_sources/native.reference.json';data=json.loads(source.read_bytes());cache={};witness=[];locked={str(source):sha(source),str(Path(__file__)):sha(__file__),str(Path(__file__).with_name('test_independent.py')):sha(Path(__file__).with_name('test_independent.py'))}
 def objects(record):
  path=ROOT.parent/record['path'];assert sha(path)==record['sha256'];locked[str(path)]=sha(path)
  if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
  return cache[path]
 for owner in ['enemy_1014_rogue','enemy_1028_mocock','enemy_1028_mocock_2','enemy_1504_cqbw']:
  record=data['enemies'][owner]['prefab'];objs=objects(record['source']);parts=record['components']
  for mode_id,item in parts.items():
   if item['native_class']!='UnitMode':continue
   actual=objs[int(mode_id)].read_typetree();assert actual==item['raw'];row={'owner':owner,'mode':int(mode_id),'actual_mode':actual,'resolved':{}}
   for key in ['_combat','_attack','_attackTrigger']:
    pointer=actual[key];assert pointer['m_FileID']==0;pid=pointer['m_PathID']
    if not pid:row['resolved'][key]=None;continue
    component=parts[str(pid)];raw=objs[pid].read_typetree();assert raw==component['raw'];script=data['native_monoscripts'][component['script_key']];script_raw=objects(script['source'])[script['path_id']].read_typetree();assert script_raw==script['raw'] and script_raw['m_ClassName']==component['native_class'];row['resolved'][key]={'path_id':pid,'actual_fields':raw,'actual_monoscript_class':script_raw['m_ClassName']}
   if owner=='enemy_1014_rogue':assert row['resolved']['_attack'] is None and row['resolved']['_attackTrigger'] is None and row['resolved']['_combat']['actual_monoscript_class']=='MultiMeleeAttack'
   else:assert row['resolved']['_combat']['path_id']==row['resolved']['_attack']['path_id'] and row['resolved']['_combat']['actual_monoscript_class']=='RangedAttack' and row['resolved']['_combat']['actual_fields']['_selectTargetSource']==2 and row['resolved']['_attackTrigger']['actual_monoscript_class']=='SelectorTrigger'
   witness.append(row)
 raw_ref=save(OUT/'raw_mode_proof.json',{'source':{'path':str(source),'sha256':sha(source)},'actual_unit_modes':witness,'scope':'fresh raw PPtr and actual referenced MonoScript typetrees; no recovered method body'})
 plugin=Rows();log=io.StringIO()
 with contextlib.redirect_stdout(log):exit_code=pytest.main(['tools/experiments/m24_peer/test_independent.py','-q','--tb=short'],plugins=[plugin])
 (OUT/'tests.log').write_text(log.getvalue(),encoding='utf8');assert exit_code==0
 actual=[]
 for level,unit,col,end,expected in [('01-11','unit/enemy_1028_mocock',4,31,[(28,170)]),('01-12','unit/enemy_1028_mocock_2',4,31,[(28,240)]),('01-11','unit/chapter01_w',4,31,[(15,460),(29,460)]),('01-12','unit/enemy_1014_rogue',3,26,[(13,165),(24,165)])]:
  fixture=h.native_fixture(level,unit,col);s=h.make(fixture);s.advance(end);assert [(e['time'],e['payload']['amount']) for e in h.events(s,'damage.accepted')]==expected;cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(3);r.advance(3);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();name=unit.split('/')[-1];actual.append({'unit':unit,'fixture':save(OUT/(name+'.fixture.json'),fixture),'commands':save(OUT/(name+'.commands.json'),s.export_replay()),'checkpoint':save(OUT/(name+'.checkpoint.json'),cp),'program':s.program.fingerprint,'runtime':s.runtime_fingerprint,'expected_damage_time_amount':expected,'checkpoint_equal':True,'commands_replay_equal':True,'observed_events':thaw([e for e in s.session.events if e['type'] in ['ability.started','damage.accepted','spatial.blocked','spatial.unblocked']])})
 assert all(sha(Path(path))==pin for path,pin in locked.items()) and implementation_digest()==CORE
 report={'schema':'ark-sim/m24-independent-fsm-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,'source_locks_start':locked,'source_locks_end':{p:sha(Path(p)) for p in locked},'source_proof':raw_ref,'tests':plugin.rows,'native_profile_actual_cases':actual,'elapsed_seconds':time.time()-start,'initial_fixture_corrections':['Original hidden target appeared at route end, so it actually retired; changed probe exit to different cell without changing visibility expectations','Original rogue was not blocked at initialization; movement tick0 precedes relationship creation. Strict independent math expected1.1*(8/30)/30 initial step, then position stable during cast1; no manual setup/replay mutation'],'native_body_verified':False,'pending':['FSM native permission/transition/cooldown movement priority','INPUT_TARGET wrapper/getter methods','packet count/splitDamage/flight profiles client comparator','M25 eligibility not part of this c4fc branch; merge needs new validation'],'scope':'bounded mathematical/profile source review and independent runtime assertions, no fullstage/native accuracy receipt','formal_approval':False};save(OUT/'review.json',report);print(json.dumps({'passed':True,'cases':len(plugin.rows),'actual_native_profiles':len(actual),'core':CORE,'report_sha256':sha(OUT/'review.json')}))
if __name__=='__main__':main()
