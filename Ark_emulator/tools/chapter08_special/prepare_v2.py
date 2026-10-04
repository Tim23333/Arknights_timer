"""Preserve failed v1 source/model/probes; fix only author adapter/API fixture errors."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'packages/campaign/chapter08_consumers/special'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
s=(HERE/'policies_v1.py').read_text().replace("params['delay_seconds']","inputs['trajectory_parameters']['delay_seconds']")
(HERE/'policies_v2.py').write_text(s,encoding='utf-8',newline='')
for name in ['emppnt','empace']:
 old=OUT/(name+'.module.v1.json');p=json.loads(old.read_bytes());p['manifest']['id']='package/ch8/'+name+'/source_v2';p['manifest']['metadata']['parent_content']={'path':str(old),'sha256':sha(old)};p['manifest']['metadata']['source_locks'][str(HERE/'policies_v2.py')]=sha(HERE/'policies_v2.py');new=OUT/(name+'.module.v2.json');assert not new.exists();new.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode())
s=(HERE/'test_author_v1.py').read_text().replace('policies_v1 import','policies_v2 import').replace('{name}.module.v1.json','{name}.module.v2.json')
s=s.replace("p['entities'].append({'id':id", "\n  if alias=='near' and blocked:components['deployable']={'base_cost':1,'capacity':1,'cooldown_seconds':0,'terrain':'ground'}\n  p['entities'].append({'id':id")
s=s.replace("{'op':'move','target':'source','row':2,'col':5}","{'op':'move','target':'source','position':{'row':2,'col':5}}")
s=s.replace("{'op':'retire','target':1}","{'op':'retire','parameters':{'reason':'controlled_source_retire'}}")
(HERE/'test_author_v2.py').write_text(s,encoding='utf-8',newline='')
s=(HERE/'verify_author_v1.py').read_text().replace('test_author_v1.py','test_author_v2.py').replace('emppnt.module.v1.json','emppnt.module.v2.json').replace('empace.module.v1.json','empace.module.v2.json').replace('author.v1.tests.json','author.v2.tests.json')
(HERE/'verify_author_v2.py').write_text(s,encoding='utf-8',newline='')
print(json.dumps({n:sha(OUT/(n+'.module.v2.json')) for n in ['emppnt','empace']}))
