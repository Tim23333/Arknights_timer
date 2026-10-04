"""Ordinary source timing correction; immutable v1 is a guarded input."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'packages/campaign/chapter06_boss/frstar2'
OUT=ROOT/'packages/campaign/chapter06_boss/frstar2_v2'
UID='unit/ch6/frstar2/3681c71c12a71fb0'
N=[f'ability/{UID}/normal{i}' for i in (0,1)]
B=[f'ability/{UID}/burst{i}' for i in (0,1)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 if sha(OLD/'model.json')!='6e889630c11b7e747828f01a56a80e5671d83dea34743d92f5f224c4526fa52a':raise ValueError('Frozen v1 model changed')
 s=json.loads((OLD/'source.closure.json').read_bytes());p=json.loads((OLD/'model.json').read_bytes())
 source_modes=[m['nodes']['_combat']['raw']['_timeMode'] for m in s['variant']['modes']]
 burst_modes=[s['components'][k]['raw']['_timeMode'] for k in ['988932605719683155','-6095939705393962925']]
 if any(type(v) is not int for v in source_modes+burst_modes) or source_modes!=[0,0] or burst_modes!=[1,1]:raise ValueError('Exact source timing modes required')
 rid='rule/'+UID+'/scaled_full_duration'
 p['rules'].append({'id':rid,'kind':'calculation_rule','contract':'ability.duration','parameters':{'minimum_speed':.01},'implementation':{'type':'expression','expression':'inputs.duration_parameters.seconds / max(inputs.attributes.attack_speed_ratio, params.minimum_speed)'}})
 for a in p['abilities']:
  if a['id'] in N:a['rules']['ability.duration']=rid
  elif a['id'] in B:a.pop('rules',None)
 meta=p['manifest']['metadata'];meta['builder_sha256']=sha(Path(__file__));meta['source_locks'][str((OLD/'model.json').relative_to(ROOT))]=sha(OLD/'model.json');meta['timing_modes']={'normal':source_modes,'burst':burst_modes,'shield':1}
 meta['reference_policies']['timing']='Native Normal TimeMode0: windup28 and full48 scale with ASPD min.01; native Burst TimeMode1 fixed28/full48 and87/full110; Shield TimeMode1 fixed55/full90. affectedBySlowDown1 preserved; TimeMode1 graphical slowdown interpretation replaceable reference/client policy. Mainattack interval standard time.interval uses actualASPD, independently probed111/.7→159.'
 meta['correction']='v1 normal windup scaled but fullbusy did not; v1 Burst wrongly bound TimeMode0 windup despite rawTimeMode1. Attributes/payloads/priority/branch/rebirth unchanged.'
 return p
if __name__=='__main__':
 OUT.mkdir(exist_ok=True);p=OUT/'model.v2.json';p.write_bytes((json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(p)}))
