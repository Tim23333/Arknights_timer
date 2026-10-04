import sys,json,hashlib,time,subprocess,io,contextlib,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m25_eligibility_candidate';BASE=ROOT.parent/'unpack_work/campaign_m23_roster_candidate';sys.path.insert(0,str(RUNTIME))
import ark_sim,pytest
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.rules.catalog import load_catalog
from ark_sim.tools.replay import replay
import test_eligibility as h
CORE='281dc1fc3fc35e83adad37146b2bfb16afa92c5086f29fc22e881f116eb80ace';OUT=ROOT/'validation/campaign/m25_eligibility';OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return {'path':str(path.relative_to(ROOT)).replace(chr(92),'/'),'sha256':sha(path)}
class Results:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.rows.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
def main():
 assert implementation_digest()==CORE;assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';start=time.time();plugin=Results();stream=io.StringIO()
 with contextlib.redirect_stdout(stream):code=pytest.main(['tools/experiments/m25_eligibility/test_eligibility.py','tests_v2/test_domain_rules.py','tests_v2/test_activation_controls.py','-q','--tb=short'],plugins=[plugin])
 (OUT/'tests.log').write_text(stream.getvalue(),encoding='utf8');assert code==0
 probes=[]
 for name,end,commands,expected in [('free',31,[(0,'target','ability/free')],True),('camouflage',31,[(0,'target','ability/camo')],True),('damage_gate',32,[(0,'target','ability/free'),(1,'source','ability/shot'),(31,'source','ability/shot')],True),('independent_union',31,[(0,'target','ability/free'),(10,'target','ability/free')],False)]:
  fixture=h.shot_fixture() if name=='damage_gate' else h.fixture();s=h.make(fixture)
  for at,source,ability in commands:s.submit({'action':'skill','source':source,'ability':ability},at=at)
  s.advance(end);before=s.checkpoint();assert h.qualifies(s)==expected;assert before==s.checkpoint();r=Engine.restore(s.program,before);s.advance(2);r.advance(2);rr=replay(s.program,s.export_replay());assert s.snapshot()==r.snapshot()==rr.snapshot()
  if name=='damage_gate':hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['time']==31 and hits[0]['payload']['amount']==10
  fixture_ref=save(OUT/(name+'.fixture.json'),fixture);commands_ref=save(OUT/(name+'.commands.json'),s.export_replay());cp_ref=save(OUT/(name+'.checkpoint.json'),before)
  probes.append({'case':name,'fixture':fixture_ref,'commands':commands_ref,'checkpoint':cp_ref,'program_fingerprint':s.program.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,'checkpoint_equal':True,'commands_replay_equal':True,'readonly_query_preserves_checkpoint':True,'expected_qualification_at_query':expected,'query_tick':end,'observed_events':thaw([e for e in s.session.events if e['type'] in ('buff.applied','buff.removed','damage.accepted','command.accepted')])})
 a=json.loads((OUT/'m23_no_config.json').read_bytes());b=json.loads((OUT/'m25_no_config.json').read_bytes());compat_keys=['fixture','world','random','scheduler','events_without_identity'];assert all(a[k]==b[k] for k in compat_keys)
 changed=[];patch=[]
 for path in sorted((RUNTIME/'ark_sim').rglob('*')):
  if path.suffix not in ('.py','.json'):continue
  rel=path.relative_to(RUNTIME);original=BASE/rel
  if not original.exists() or sha(path)!=sha(original):
   changed.append({'path':str(rel).replace(chr(92),'/'),'base_sha256':sha(original) if original.exists() else None,'candidate_sha256':sha(path)})
   patch.extend(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True) if original.exists() else [],path.read_text(encoding='utf8').splitlines(True),fromfile='a/'+str(rel).replace(chr(92),'/'),tofile='b/'+str(rel).replace(chr(92),'/')))
 (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8');save(OUT/'changed_files.json',changed);assert implementation_digest()==CORE
 report={'schema':'ark-sim/m25-eligibility-candidate-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'actual_runtime_module':ark_sim.__file__,'base_runtime':'../unpack_work/campaign_m23_roster_candidate','base_implementation_sha256':a['core'],'contracts':len(load_catalog()['contracts']),'tests':plugin.rows,'elapsed_seconds':time.time()-start,'actual_command_probes':probes,'no_config_compatibility':{'keys_equal':compat_keys,'event_count':len(a['events_without_identity']),'raw_events_equal':a['events_raw_sha256']==b['events_raw_sha256'],'identity_normalization':a['identity_normalization'],'references':[{'path':'validation/campaign/m25_eligibility/'+n,'sha256':sha(OUT/n)} for n in ('m23_no_config.json','m25_no_config.json')]},'source_locks':{str(p.relative_to(ROOT)).replace(chr(92),'/'):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_eligibility.py'),Path(__file__).with_name('build_profiles.py'),ROOT/'validation/campaign/advanced_selector_source_audit.json',ROOT/'packages/campaign/selector_eligibility/m25.source_profiles.json']},'changed_files':changed,'patch_sha256':sha(OUT/'candidate.patch'),'client_verified':False,'native_body_pending':['ValidateTarget/get_isTargetFree/get_isCamouflage','Trigger_GetSelector/AttackWrapper input target','source-relative Side2 and neutral policy','partial cause aggregate and declared defaults'],'scope':'model eligibility math plus exact source enums/fields/PPTR; not fullstage or gameplay accuracy receipt','formal_approval':False}
 save(OUT/'candidate_final.json',report);print(json.dumps({'passed':True,'tests':len(plugin.rows),'core':CORE,'probes':len(probes),'report_sha256':sha(OUT/'candidate_final.json')}))
if __name__=='__main__':main()
