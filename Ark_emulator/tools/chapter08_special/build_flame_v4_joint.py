"""Exact contentflag fix; no source/entity/projectile/runtime mutation."""
import hashlib,json
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'packages/campaign/chapter08_consumers/flame'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parent=OUT/'module.v3.joint.json';assert sha(parent)=='297a69559ebed3c062108451b6ede92c08279daea41453b58355145919b20ba1';p=json.loads(parent.read_bytes());source=ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v2.json';raw=json.loads(source.read_bytes())['bson_templates']['templates']['flame_s'];node=raw['parsed']['eventToActions']['ON_BUFF_START'][0];assert node['_considerUnhurtable'] is False and node['_skipModifierEvent'] is False and node['_noSourceDamage'] is False
 before=deepcopy(p['abilities']);changed=[]
 for a in p['abilities']:
  for index,e in enumerate(a['timeline']):
   effect=e['effect']
   if effect['op']=='damage' and effect.get('rules',{}).get('damage.pipeline')=='rule/ch8/flame/damage':
    assert 'parameters' not in effect;effect['parameters']={'consider_unhurtable':False};changed.append({'ability':a['id'],'entry':index})
 assert len(changed)==4
 check=deepcopy(p['abilities'])
 for a in check:
  for e in a['timeline']:
   if e['effect']['op']=='damage' and e['effect'].get('rules',{}).get('damage.pipeline')=='rule/ch8/flame/damage':e['effect'].pop('parameters')
 assert check==before
 p['manifest']['id']='package/ch8/flame/source_v4_joint';m=p['manifest']['metadata'];m['parent_content']={'path':str(parent),'sha256':sha(parent)};m['source_flag_fix']={'source_BSON_document_sha256':raw['document_sha256'],'source_node':node,'changed':changed,'scope':'Explicit false propagates through existing damage hooks; does not skipModifierEvent or modify sourceHP/ATK/SP/rays.'};m['source_locks'][str(Path(__file__))]=sha(Path(__file__));m['source_locks'][str(parent)]=sha(parent);m['source_locks'][str(source)]=sha(source)
 out=OUT/'module.v4.joint.json';assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'changed_packets':len(changed),'entities_projectiles_preserved':True}))
if __name__=='__main__':main()
