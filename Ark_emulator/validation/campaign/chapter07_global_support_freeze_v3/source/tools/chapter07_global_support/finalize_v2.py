"""New exact source consumer identity on frozen 4f16; old 7696 author input remains."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 old=ROOT/'packages/campaign/chapter07_global_support/sotidp.module.v1.json';p=json.loads(old.read_bytes());source=ROOT/'packages/campaign/chapter07_sources/native.reference.json';d=json.loads(source.read_bytes());v=d['variants']['enemy_1080_sotidp@0/ec07f90cc02c1801'];combat=v['modes'][0]['nodes']['_combat'];rule=next(r for r in p['rules'] if r['contract']=='ability.windup');oldid=rule['id'];newid='rule/ch7/global/sotidp/source_windup';text=json.dumps(p).replace(oldid,newid);p=json.loads(text);rule=next(r for r in p['rules'] if r['id']==newid);rule['metadata']['source_timing_fields']={k:combat['raw'][k] for k in ('_affectedBySlowDown','_timeMode','_waitForAttackEvent','_maxAnimScale','_preDelay','_animKey')};p['manifest']['id']='package/ch7/global/sotidp/v2';p['manifest']['metadata']['required_runtime']='4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346';p['manifest']['metadata']['source_locks'].update({str(old):sha(old),str(Path(__file__)):sha(Path(__file__))});out=old.with_name('sotidp.module.v2.json');assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out)}))
if __name__=='__main__':main()
