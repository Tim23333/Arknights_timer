"""Independent same fixture controls for actual-input guard and durable failure."""
import sys,json,hashlib,runpy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim.adapters.api import implementation_digest
from ark_sim import Compiler
OUT=ROOT/'validation/campaign/m26_content_peer/stream_v2';OUT.mkdir(parents=True,exist_ok=True)
fixture_path=ROOT/'validation/campaign/m26_content_peer/stream_input_identity/input.json';raw=fixture_path.read_bytes();p=json.loads(raw);assert p['scenarioDraft']['seed']==71
commands_raw=b'[]\n';commands_altered=b'[{"at":1,"action":"withdraw","source":"missing"}]\n';modified=json.loads(raw);modified['scenarioDraft']['seed']=72;altered=(json.dumps(modified,ensure_ascii=False,indent=2)+'\n').encode()
runner=ROOT/'tools/run_campaign_streaming_runthrough_v2.py';helper=ROOT/'tools/campaign_streaming_evidence.py';native_read=Path.read_bytes
sha=lambda b:hashlib.sha256(b).hexdigest()
before={'core':implementation_digest(),'runner':sha(native_read(runner)),'helper':sha(native_read(helper)),'fixture':sha(raw),'peer':sha(native_read(Path(__file__)))}
rows=[]
for case in ('baseline','old_second_read_attack','alter_actual_decode_only','commands_decode_drift','helper_drift'):
 folder=OUT/case;folder.mkdir(exist_ok=True);input_path=folder/'input.json';input_path.write_bytes(raw);commands=folder/'commands.json';commands.write_bytes(commands_raw);output=folder/'report.json';counts={}
 def intercepted(self):
  name=self.resolve();counts[str(name)]=counts.get(str(name),0)+1;n=counts[str(name)]
  if name==input_path.resolve():
   if case=='old_second_read_attack' and n==2:return altered
   if case=='alter_actual_decode_only' and n==1:return altered
  if name==commands.resolve() and case=='commands_decode_drift' and n==1:return commands_altered
  if name==helper.resolve() and case=='helper_drift' and n>=2:return native_read(self)+b'\n# independent simulated source drift\n'
  return native_read(self)
 sys.argv=['run_campaign_streaming_runthrough_v2.py','--runtime-root',str(RUNTIME),'--expected-core',before['core'],'--package',str(input_path),'--commands',str(commands),'--output',str(output),'--max-ticks','100','--checkpoint-at','2']
 with patch.object(Path,'read_bytes',intercepted):
  try:runpy.run_path(str(runner),run_name='__main__')
  except SystemExit as e:exit_code=e.code
 report=json.loads(native_read(output));expected_raw=altered if case=='alter_actual_decode_only' else raw
 assert report['package_sha256']==sha(expected_raw) and report['decoded_input_sha256'][str(input_path.resolve())]==sha(expected_raw)
 expected_commands=commands_altered if case=='commands_decode_drift' else commands_raw
 assert report['commands_sha256']==sha(expected_commands) and report['decoded_input_sha256'][str(commands.resolve())]==sha(expected_commands)
 assert report['program']==Compiler().compile(json.loads(expected_raw)).fingerprint
 assert report['process_complete'] and report['state']['leaks']==2 and report['base_life_final']==99997
 assert report['checkpoint_equal'] is True and report['replay_equal'] is True
 assert report['passed'] is (case=='baseline') and report['identity_stable'] is (case=='baseline')
 assert exit_code==(0 if case=='baseline' else 1)
 journal=report['journal'];data=native_read(Path(journal['path']));events=[json.loads(line) for line in data.splitlines()]
 assert len(events)==journal['events']==report['observations']['event_count'] and sha(data)==journal['sha256']
 rows.append({'case':case,'runner_exit':exit_code,'report_sha256':sha(native_read(output)),'package_actual_decoded_sha256':sha(expected_raw),'identity_stable':report['identity_stable'],'passed':report['passed'],'process_complete':True,'checkpoint_equal':True,'replay_equal':True,'report':str(output),'actual_read_counts':counts})
after={'core':implementation_digest(),'runner':sha(native_read(runner)),'helper':sha(native_read(helper)),'fixture':sha(native_read(fixture_path)),'peer':sha(native_read(Path(__file__)))}
assert before==after
proof={'schema_version':1,'scope':'independent runner actual-input/identity/journal guard only, synthetic two leaks, not stage or native receipt','passed':True,'source_start':before,'source_end':after,'cases':rows,'fixture_original':p,'altered_decode_fixture':modified,'formal_approved':False}
(OUT/'final.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'cases':len(rows),'sha256':sha(native_read(OUT/'final.json'))}))
