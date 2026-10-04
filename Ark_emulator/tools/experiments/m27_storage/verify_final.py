import sys,json,hashlib,time,io,contextlib,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate';BASE=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate';OUT=ROOT/'validation/campaign/m27_storage';sys.path.insert(0,str(RUNTIME))
import ark_sim,pytest
from ark_sim.adapters.api import implementation_digest
CORE='75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
class Rows:
 def __init__(self):self.rows=[]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.rows.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
def main():
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';guards=[Path(__file__),ROOT/'tools/experiments/m27_storage/test_storage.py',ROOT/'tools/experiments/m27_storage/capture_v2.py',ROOT/'tools/experiments/m27_storage/compare_values.py',RUNTIME/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/content/presets/ark_standard.json'];before={str(p):sha(p) for p in guards};plugin=Rows();log=io.StringIO();begun=time.time()
 with contextlib.redirect_stdout(log):code=pytest.main(['tools/experiments/m27_storage/test_storage.py','tests_v2/test_kernel.py','tests_v2/test_replay.py','tests_v2/test_m6_kernel_review.py','-q','--tb=short'],plugins=[plugin])
 (OUT/'final_tests.log').write_text(log.getvalue(),encoding='utf8');assert code==0
 old=json.loads((OUT/'m26_01_12_prefix300.json').read_bytes());new=json.loads((OUT/'m27_01_12_prefix300.json').read_bytes());lv=json.loads((OUT/'m26.capture_v2.json').read_bytes());rv=json.loads((OUT/'m27.capture_v2.json').read_bytes());cmp=json.loads((OUT/'all_values_capture_v2.json').read_bytes());assert cmp['passed'] and cmp['all_events_full_fields_typed_equal'] and cmp['excluded_payload_fields']==[] and cmp['actual_decoded_byte_identity_bound']
 for report in (lv,rv):
  for key in ('actual_decoded_package_bytes','actual_decoded_commands_bytes'):
   assert sha(Path(report[key]['path']))==report[key]['sha256']
 changes=[];patch=[]
 for path in sorted((RUNTIME/'ark_sim').rglob('*')):
  if path.suffix not in ('.py','.json'):continue
  rel=path.relative_to(RUNTIME);original=BASE/rel
  if not original.exists() or sha(original)!=sha(path):
   changes.append({'path':str(rel).replace(chr(92),'/'),'old_sha256':sha(original) if original.exists() else None,'new_sha256':sha(path)});patch.extend(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True) if original.exists() else [],path.read_text(encoding='utf8').splitlines(True),fromfile='a/'+str(rel).replace(chr(92),'/'),tofile='b/'+str(rel).replace(chr(92),'/')))
 (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8');after={str(p):sha(p) for p in guards};assert before==after and implementation_digest()==CORE
 a,b=old['points'][-1],new['points'][-1];result={'schema':'ark-sim/m27-storage-candidate-review/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'actual_module':ark_sim.__file__,'base_core':'7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe','tests':plugin.rows,'test_seconds':time.time()-begun,'source_before':before,'source_after':after,'changed_files':changes,'patch_sha256':sha(OUT/'candidate.patch'),'all_values_comparison':{'path':'validation/campaign/m27_storage/all_values_capture_v2.json','sha256':sha(OUT/'all_values_capture_v2.json')},'retention':{'tick':300,'events':47370,'source_rss':a['rss_before_census'],'candidate_rss':b['rss_before_census'],'source_retained_estimate':a['journal_census']['estimated_retained_shallow_bytes_including_mapping_backings'],'candidate_retained_estimate':b['journal_census']['estimated_retained_shallow_bytes_including_mapping_backings'],'source_containers':a['journal_census']['unique_json_container_identities'],'candidate_containers':b['journal_census']['unique_json_container_identities']},'actual_advance_performance':{'source_cpu_seconds':lv['advance_cpu_seconds'],'candidate_cpu_seconds':rv['advance_cpu_seconds'],'ratio':rv['advance_cpu_seconds']/lv['advance_cpu_seconds'],'source_wall_seconds':lv['advance_wall_seconds'],'candidate_wall_seconds':rv['advance_wall_seconds'],'total_census_time_not_used_to_mask_advance_cost':True},'cache_budget':'<=65536entries and32MiB conservative summed-descendant weighted value/key cost, plus bounded O(entries) bookkeeping; not RSS cap','cache':rv['cache'],'next_optimization_pending':'current rollback clears performance cache even on normal ActivationRejected; separate future candidate required, never alter this frozen implementation','scope':'all event/value storage conservation and bounded mathematical CP/replay; no native correctness or fullstage receipt','formal_approval':False};(OUT/'candidate_final.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'tests':len(plugin.rows),'core':CORE,'report_sha256':sha(OUT/'candidate_final.json'),'patch_sha256':sha(OUT/'candidate.patch')}))
if __name__=='__main__':main()
