"""Deterministic TOCTOU counterexample without editing the frozen runner."""
import sys,json,hashlib,runpy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/m26_content_peer/stream_input_identity';OUT.mkdir(parents=True,exist_ok=True)
p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard'],'metadata':{'pending_model_gaps':[]}},'entities':[{'id':'unit/flow','kind':'entity','tags':['enemy','ground'],'components':{'attributes':{'base':{'max_hp':17,'move_speed':30}},'resources':{'hp':{'initial':17,'capacity':17,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':1}}}], 'scenarioDraft':{'id':'scenario/peer_stream','ruleset':'ruleset/ark_standard','seed':71,'map':{'rows':1,'cols':3},'resources':{'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},'metadata':{'runthrough_profile':{'base_life_resource':'life','peer_probe':True}},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','count':2,'interval_seconds':.06666666666666667,'spawn':{'definition':'unit/flow','position':{'row':0,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':2},'checkpoints':[]}}}]}]}]}}}
raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();input_path=OUT/'input.json';input_path.write_bytes(raw);commands=OUT/'commands.json';commands.write_bytes(b'[]\n')
modified=json.loads(raw);modified['scenarioDraft']['seed']=72;actual=(json.dumps(modified,ensure_ascii=False,indent=2)+'\n').encode()
raw_read=Path.read_bytes;reads=0
def intercepted(self):
 global reads
 if self.resolve()==input_path.resolve():
  reads+=1
  if reads==2:return actual # actual decode, between separate SHA reads
 return raw_read(self)
sys.argv=['run_campaign_streaming_runthrough.py','--runtime-root',str(RUNTIME),'--expected-core',implementation_digest(),'--package',str(input_path),'--commands',str(commands),'--output',str(OUT/'runner.json'),'--max-ticks','100','--checkpoint-at','2']
with patch.object(Path,'read_bytes',intercepted):
 try:runpy.run_path(str(ROOT/'tools/run_campaign_streaming_runthrough.py'),run_name='__main__')
 except SystemExit as e:exit_code=e.code
report=json.loads((OUT/'runner.json').read_bytes());proof={'counterexample_reproduced':report['passed'] and report['identity_stable'] and report['package_sha256']==hashlib.sha256(raw).hexdigest() and report['program']==Compiler().compile(modified).fingerprint and report['program']!=Compiler().compile(p).fingerprint,'runner_exit':exit_code,'package_read_calls':reads,'advertised_source_sha256':report['package_sha256'],'actual_decoded_bytes_sha256':hashlib.sha256(actual).hexdigest(),'disk_bytes_sha256':hashlib.sha256(raw_read(input_path)).hexdigest(),'reported_program':report['program'],'disk_program':Compiler().compile(p).fingerprint,'actual_program':Compiler().compile(modified).fingerprint,'reported_seed':report['seed'],'reported_identity_stable':report['identity_stable'],'reported_passed':report['passed'],'fixture':p,'actual_decode_fixture':modified,'scope':'input guard flaw only; no source/core changes; synthetic read injection models file replacement race'}
(OUT/'counterexample.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:proof[k] for k in ('counterexample_reproduced','reported_identity_stable','reported_passed','reported_seed')}));raise SystemExit(0 if proof['counterexample_reproduced'] else 1)
