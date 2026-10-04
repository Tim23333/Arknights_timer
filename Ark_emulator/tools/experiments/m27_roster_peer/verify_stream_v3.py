"""Actual disk reload preserves z,a execution order; drift failure is durable."""
import sys,json,hashlib,runpy,traceback
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m27_event_intern_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim.adapters.api import implementation_digest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
OUT=ROOT/'validation/campaign/m27_roster_peer/stream_v3';OUT.mkdir(parents=True,exist_ok=True)
old=ROOT/'validation/campaign/m26_content_peer/stream_input_identity/input.json';p=json.loads(old.read_bytes());p['entities'].append({'id':'unit/clock','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100},'z':{'initial':0,'capacity':1000,'recovery_rate':1},'a':{'initial':0,'capacity':1000,'recovery_rate':2}},'spatial':{}}});p['scenarioDraft']['initialEntities']=[{'definition':'unit/clock','instanceAlias':'clock','position':{'row':0,'col':0}}]
raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();cmd_raw=b'[]\n';cmd_altered=b'[{"at":1,"action":"withdraw","source":"missing"}]\n';modified=json.loads(raw);modified['scenarioDraft']['seed']=72;altered=(json.dumps(modified,ensure_ascii=False,indent=2)+'\n').encode()
runner=ROOT/'tools/run_campaign_streaming_runthrough_v3.py';helper=ROOT/'tools/campaign_streaming_evidence.py';ordered=ROOT/'tools/campaign_ordered_checkpoint.py';native_read=Path.read_bytes;sha=lambda b:hashlib.sha256(b).hexdigest()
before={'core':implementation_digest(),'runner':sha(native_read(runner)),'helper':sha(native_read(helper)),'ordered':sha(native_read(ordered)),'peer':sha(native_read(Path(__file__)))}
assert before['core']=='75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90';rows=[]
for case in ('baseline_ordered','old_second_read_attack','actual_decode_drift','commands_decode_drift','helper_drift','checkpoint_second_load_drift'):
 folder=OUT/case;folder.mkdir(exist_ok=True);input_path=folder/'input.json';input_path.write_bytes(raw);commands=folder/'commands.json';commands.write_bytes(cmd_raw);output=folder/'report.json';cp_path=output.with_suffix('.checkpoint.json');counts={}
 def intercepted(self):
  name=self.resolve();counts[str(name)]=counts.get(str(name),0)+1;n=counts[str(name)]
  if name==input_path.resolve():
   if case=='old_second_read_attack' and n==2:return altered
   if case=='actual_decode_drift' and n==1:return altered
  if name==commands.resolve() and case=='commands_decode_drift' and n==1:return cmd_altered
  if name==helper.resolve() and case=='helper_drift' and n>=2:return native_read(self)+b'\n# simulated drift\n'
  if name==cp_path.resolve() and case=='checkpoint_second_load_drift' and n==2:return native_read(self)+b' '
  return native_read(self)
 sys.argv=['run_campaign_streaming_runthrough_v3.py','--runtime-root',str(RUNTIME),'--expected-core',before['core'],'--package',str(input_path),'--commands',str(commands),'--output',str(output),'--max-ticks','100','--checkpoint-at','2']
 error=None;exit_code=None
 with patch.object(Path,'read_bytes',intercepted):
  try:runpy.run_path(str(runner),run_name='__main__')
  except SystemExit as e:exit_code=e.code
  except Exception as e:error=type(e).__name__+': '+str(e)
 if case=='checkpoint_second_load_drift':
  assert error and 'Durable checkpoint bytes changed' in error
  row={'case':case,'correctly_rejected':True,'error':error,'final_failure_report_exists':output.exists(),'expected_failure_report_exists':True,'failure_report_gate_satisfied':output.exists(),'actual_read_counts':counts}
  (folder/'peer_error.json').write_text(json.dumps(row,indent=2)+'\n',encoding='utf8');rows.append(row);continue
 report=json.loads(native_read(output));expected_raw=altered if case=='actual_decode_drift' else raw;expected_cmd=cmd_altered if case=='commands_decode_drift' else cmd_raw
 assert report['package_sha256']==sha(expected_raw) and report['commands_sha256']==sha(expected_cmd)
 assert report['program']==Compiler().compile(json.loads(expected_raw)).fingerprint
 assert report['process_complete'] and report['state']['leaks']==2 and report['base_life_final']==99997
 assert report['checkpoint_equal'] is True and report['durable_checkpoint_equal'] is True and report['replay_equal'] is True
 assert report['passed'] is (case=='baseline_ordered') and report['identity_stable'] is (case=='baseline_ordered')
 assert exit_code==(0 if case=='baseline_ordered' else 1)
 cp_raw=native_read(cp_path);assert sha(cp_raw)==report['checkpoint_sha256'];checkpoint=json.loads(cp_raw)
 # Recreate from the actual saved bytes and prove exact future resource event order independently.
 program=Compiler().compile(json.loads(expected_raw));sim=Engine.restore(program,checkpoint);sim.advance(2)
 changed=[e['payload']['resource'] for e in sim.session.events if e['type']=='resource.changed' and e['time']==2 and e['payload']['target']==sim.session.world.resolve('clock')];assert changed==['z','a']
 journal_raw=native_read(Path(report['journal']['path']));events=[json.loads(line) for line in journal_raw.splitlines()];assert len(events)==report['journal']['events']==report['observations']['event_count'] and sha(journal_raw)==report['journal']['sha256']
 rows.append({'case':case,'passed_expected_gate':True,'runner_exit':exit_code,'reported_passed':report['passed'],'identity_stable':report['identity_stable'],'durable_checkpoint_equal':True,'replay_equal':True,'checkpoint_bytes_sha256':sha(cp_raw),'report_sha256':sha(native_read(output)),'post_disk_restore_resource_order':changed,'report':str(output),'actual_read_counts':counts})
after={'core':implementation_digest(),'runner':sha(native_read(runner)),'helper':sha(native_read(helper)),'ordered':sha(native_read(ordered)),'peer':sha(native_read(Path(__file__)))};assert before==after
proof={'schema_version':1,'scope':'independent streaming v3 ordered actual-byte CP/input guard peer, no stage/native approval','five_identity_cases_passed':True,'checkpoint_drift_rejected':True,'checkpoint_failure_report_durable':rows[-1]['failure_report_gate_satisfied'],'source_start':before,'source_end':after,'cases':rows,'fixture_original':p,'fixture_changed_decode':modified,'formal_approved':False};(OUT/'final.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'identity_cases_passed':True,'checkpoint_drift_rejected':True,'durable_failure_report':proof['checkpoint_failure_report_durable'],'sha256':sha(native_read(OUT/'final.json'))}))
