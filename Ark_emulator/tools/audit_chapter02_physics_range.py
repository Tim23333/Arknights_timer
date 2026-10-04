"""Recover exact serialized PhysicsRange transforms; do not invent map axes."""
from pathlib import Path
import json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json';OUT=ROOT/'packages/campaign/chapter02_behavior/aoemag.physics.reference.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 import UnityPy
 d=json.loads(SOURCE.read_bytes());p=d['prefabs']['enemy_1018_aoemag'];path=ROOT.parent/p['source']['path'];assert sha(path)==p['source']['sha256']
 objects={o.path_id:o for o in UnityPy.load(str(path)).objects};nodes=p['components'];physics=[(pid,c) for pid,c in nodes.items() if c['native_class']=='PhysicsRange'];assert len(physics)==1
 pid,range_node=physics[0];assert objects[int(pid)].read_typetree()==range_node['raw'];go=range_node['gameobject_path_id']
 transforms={r['gameobject_path_id']:r for r in p['geometry_sources'] if r['unity_type']=='Transform'}
 colliders=[]
 for row in p['geometry_sources']:
  if row['gameobject_path_id']!=go or 'Collider' not in row['unity_type']:continue
  assert objects[row['path_id']].read_typetree()==row['raw'];chain=[];current=go
  while current in transforms:
   t=transforms[current];assert objects[t['path_id']].read_typetree()==t['raw'];chain.append(t)
   parent=t['raw']['m_Father']['m_PathID']
   # m_Father references a Transform, not a GameObject.
   matches=[g for g,tr in transforms.items() if tr['path_id']==parent]
   if not parent:break
   if len(matches)!=1:raise ValueError('exact PhysicsRange parent transform unresolved')
   current=matches[0]
  colliders.append({'source_collider':row,'local_to_root_transform_chain':chain})
 assert len(colliders)==2 and all(c['source_collider']['unity_type']=='BoxCollider2D' for c in colliders)
 combat=[c for c in nodes.values() if c['native_class']=='MeleeAttack'];assert len(combat)==1
 selector=nodes[str(combat[0]['raw']['_selector']['m_PathID'])];assert selector['native_class']=='AdvancedSelector' and selector['gameobject_path_id']==go
 return {'schema':'ark-sim/chapter02-physics-source/v1','source':p['source'],'source_package_sha256':sha(SOURCE),'builder_sha256':sha(__file__),'physics_range_component':{'path_id':pid,**range_node},'actual_combat':combat[0],'actual_selector':selector,'colliders':colliders,'native_axes':{'unity_collider_axes':'serialized local x/y; z and quaternion/scale preserved','native_map_coordinate_mapping':'unresolved method body; no axis projection applied','runtime_profile':None},'model_gaps':['pure multi-box overlap target origin/transform/mount policy not declared','capsule/body overlap vs center-point tests not same geometry'],'client_pending':['native PhysicsRange GetTargets/TriggerHit and transform-to-world methods','native movement/height axes and dynamic animation mount transform'],'not_executable':True,'formal_approved':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'boxes':len(p['colliders']),'chain_lengths':[len(c['local_to_root_transform_chain']) for c in p['colliders']],'sha256':sha(OUT)}))
