import json,hashlib
from pathlib import Path
import UnityPy
ROOT=Path(__file__).resolve().parents[3]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
emp=json.loads((ROOT/'packages/campaign/chapter01_devices/emp.source.json').read_bytes());wrapper=json.loads((ROOT/'packages/campaign/chapter01_devices/emp.terrain.json').read_bytes());asset=ROOT.parent/emp['prefab']['source']['path'];assert sha(asset)==emp['prefab']['source']['sha256'];objects={o.path_id:o for o in UnityPy.load(str(asset)).objects};trap=None;mode=None;actual=[]
for pid,c in emp['prefab']['components'].items():
 if c['native_class'] in ('TrapMode','MapDependentTrap'):
  tree=objects[int(pid)].read_typetree();assert tree==c['raw'];actual.append({'class':c['native_class'],'path_id':int(pid),'raw':tree})
  if c['native_class']=='TrapMode':mode=tree
  else:trap=tree
layer=wrapper['entities'][0]['components']['terrain_overlays'][0]
assert layer['values']=={'buildableType':mode['_tileOptions']['buildableType'],'physicalHeight':mode['_rewriteHeight'],'obstacleLikeMoveCost':bool(mode['_tileOptions']['overrideObstacleLikeMoveCost'])}
assert mode['_keepCurrentPassableMask']==1 and mode['_rewriteTileHeightType']==0 and mode['_rewriteTileHeight']==1 and mode['_rewriteTileAdvancedBuildMask']==0 and layer['preserve']==['passableMask','heightType','advancedBuildMask']
assert trap['_rewriteTileOptions']==1 and trap['_occupiedRemainingCharacterCnt']==0 and trap['_withdrawable']==1 and wrapper['entities'][0]['components']['deployable']['parameters']['advanced_build_mask']==trap['_buildCondition']['advancedBuildableMask']
portal=json.loads((ROOT/'validation/campaign/chapter01_portal_source_audit.json').read_bytes());a=ROOT.parent/portal['tile_asset']['path'];assert sha(a)==portal['tile_asset']['sha256'];objects={o.path_id:o for o in UnityPy.load(str(a)).objects}
for p in portal['prefabs']:
 assert objects[p['game_object_path_id']].read_typetree()==p['raw_game_object']
 for c in p['components']:assert objects[c['path_id']].read_typetree()==c['raw']
source=json.loads((ROOT/'packages/campaign/chapter01_sources/native.reference.json').read_bytes());native=source['stages']['level_main_01-12']['native_level_document'];used={a['routeIndex'] for w in native['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='SPAWN'};assert set(portal['used_spawn_route_indices'])==used and len({r['route_index'] for r in portal['route_associations']})==8
model=json.loads((ROOT/'packages/campaign/chapter01_stage_models/m18/level_main_01-12.portal.partial.json').read_bytes());profiles=model['scenarioDraft']['map']['tile_mechanics'];assert profiles['tile_telin']['role']=='entry' and profiles['tile_telout']['role']=='exit'
assert len(portal['route_associations'])==9 and all(r['route_index'] in used for r in portal['route_associations'])
report={'schema':'ark-sim/independent-terrain-portal-raw-review/v1','passed':True,'actual_EMP_components':actual,'source_locks':[{'path':str(asset),'sha256':sha(asset)},{'path':str(a),'sha256':sha(a)}],'portal_actual_prefab_count':len(portal['prefabs']),'actual_all_used_route_count':len(used),'actual_portal_used_route_count':8,'actual_portal_pair_count':len(portal['route_associations']),'numeric_height_has_no_3D_physics_claim':True,'native_method_bodies_recovered':False,'formal_approval':False,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(__file__),'result':'passed'}]}
p=ROOT/'validation/campaign/m16_m18_peer/raw_sources.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'EMP_components':len(actual),'portal_pairs':9}))
