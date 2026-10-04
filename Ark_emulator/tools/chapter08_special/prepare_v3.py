"""Correct selected-point projectile target and let real blocker settlement precede combat selection."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'packages/campaign/chapter08_consumers/special'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['emppnt','empace']:
 old=OUT/(name+'.module.v2.json');p=json.loads(old.read_bytes());p['manifest']['id']='package/ch8/'+name+'/source_v3';p['manifest']['metadata']['parent_content']={'path':str(old),'sha256':sha(old)};p['manifest']['metadata']['source_locks'][str(Path(__file__))]=sha(Path(__file__))
 if name=='emppnt':
  p['abilities'][0]['timeline'][0]['effect'].pop('target');p['manifest']['metadata']['reference_policy']['projectile_target_binding']='Original selected target launches projectile to captured target point; area center_position is supplied by real impact. Source target:self is inappropriate here and only made one target near the shooter take damage in v2.'
 else:
  p['abilities'][0]['activation'].pop('condition');p['manifest']['metadata']['reference_policy']['combat_settlement']='Attempt actual blocker-only combat with settle_blocking True before selection; no initial blocked_by condition prevents first-tick settlement. Invalid blocker produces no target and no ranged fallback after its own live unblocked guard.'
 out=OUT/(name+'.module.v3.json');assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode())
s=(HERE/'test_author_v2.py').read_text().replace('{name}.module.v2.json','{name}.module.v3.json')
s=s.replace("p['entities'][0]['components']['resources']['hp']['initial']=24000;d=fixed_damage(p,12000)","fill=ability(p,'fill_maxhp',{'op':'modify_resource','resource':'hp','delta':12000});d=fixed_damage(p,12000)")
s=s.replace("a=ability(p,'silence',{'op':'apply_buff','buff':sil});s=make(p);s.submit", "a=ability(p,'silence',{'op':'apply_buff','buff':sil});s=make(p);s.submit({'action':'skill','source':'near','ability':fill},at=1);s.submit")
(HERE/'test_author_v3.py').write_text(s,encoding='utf-8',newline='')
s=(HERE/'verify_author_v2.py').read_text().replace('test_author_v2.py','test_author_v3.py').replace('module.v2.json','module.v3.json').replace('author.v2.tests.json','author.v3.tests.json')
(HERE/'verify_author_v3.py').write_text(s,encoding='utf-8',newline='')
print(json.dumps({name:sha(OUT/(name+'.module.v3.json')) for name in ['emppnt','empace']}))
