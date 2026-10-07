"""Bind each native root/mover/windup and all source fields; preserve v1 drafts."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 src=ROOT/'packages/campaign/chapter07_sources/native.reference.json';d=json.loads(src.read_bytes());outputs=[]
 for parent in (ROOT/'packages/campaign/chapter07_strength_melee').glob('*.v1.json'):
  p=json.loads(parent.read_bytes());vid=p['manifest']['metadata']['variant_bindings'][0]['variant_id'];v=d['variants'][vid];pf=d['prefabs'][v['prefab_key']];root=next(c for c in pf['components'].values() if c['native_class']=='Enemy');mover=next(c for c in pf['components'].values() if c['native_class']=='MoveController');raw=v['modes'][0]['nodes']['_combat']['raw'];unit=p['entities'][0];unit['components']['attributes']['base']['block_cost']=root['raw']['_blockVolume'];unit['components']['spatial']['steering']['parameters'].update(response_factor=mover['raw']['_steeringFactor'],max_acceleration=mover['raw']['_maxSteeringForce']);unit['components']['lifecycle']['leak_loss']=v['native_enemy']['resolved']['lifePointReduce'];p['manifest']['metadata']['variant_bindings'][0].update(root_source=root,mover_source=mover,combat_source=v['modes'][0]['nodes']['_combat']);wind=next(r for r in p['rules'] if r['contract']=='ability.windup');wind['parameters']['native_max_anim_scale']=raw['_maxAnimScale'];wind['metadata']['source_timing_fields']={k:raw[k] for k in ('_affectedBySlowDown','_timeMode','_waitForAttackEvent','_maxAnimScale','_preDelay','_animKey')};p['manifest']['metadata']['source_locks'].update({str(parent):sha(parent),str(Path(__file__)):sha(Path(__file__))});p['manifest']['id']=p['manifest']['id'].replace('/v1','/v2');out=parent.with_name(parent.name.replace('.v1.json','.v2.json'));assert not out.exists();out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');outputs.append({'path':str(out),'sha':sha(out)})
 print(json.dumps(outputs))
if __name__=='__main__':main()
