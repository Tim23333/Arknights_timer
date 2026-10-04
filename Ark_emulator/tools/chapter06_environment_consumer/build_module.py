"""Exact native fence/portal source profiles, map masks and unshortened route operands."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));OUT=ROOT/'packages/campaign/chapter06_environment_consumer'
from tools.build_reference_stage_scenario_v2 import map_plan,route_ir
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=ROOT/'packages/campaign/chapter06_environment/source.reference.json';plan=ROOT/'packages/campaign/chapter06_plans/source.plan.json';s=json.loads(source.read_bytes());p=json.loads(plan.read_bytes());locks={str(source):sha(source),str(plan):sha(plan),str(ROOT/'tools/build_reference_stage_scenario_v2.py'):sha(ROOT/'tools/build_reference_stage_scenario_v2.py')};locks.update({str((ROOT.parent/n).resolve()):h for n,h in s['source_locks'].items()});assert all(sha(Path(n))==h for n,h in locks.items());stages={}
 for name,stage in p['stages'].items():
  native=stage['native_document'];mp=map_plan(native);cells={k:[{'row':i//mp['cols'],'col':i%mp['cols'],'options':t} for i,t in enumerate(mp['tiles']) if t['tileKey']==k] for k in ('tile_fence','tile_telin','tile_telout')};routes={str(i):route_ir(native['routes'][i],mp['rows']) for i in stage['used_routes']};pairs=[]
  for i in stage['used_routes']:
   route=routes[str(i)];last=route['startPosition'];hidden=False;entry=None
   for ci,c in enumerate(route['checkpoints']):
    if c['type']=='MOVE':last=c['position']
    elif c['type']=='DISAPPEAR':
     assert not hidden;hidden=True;entry=deepcopy(last);assert mp['tiles'][entry['row']*mp['cols']+entry['col']]['tileKey']=='tile_telin'
    elif c['type']=='APPEAR_AT_POS':
     assert hidden;exit=deepcopy(c['position']);assert mp['tiles'][exit['row']*mp['cols']+exit['col']]['tileKey']=='tile_telout';pairs.append({'native_route':i,'appear_checkpoint':ci,'entry':entry,'exit':exit,'raw_appear':deepcopy(native['routes'][i]['checkpoints'][ci])});hidden=False;last=exit
  profiles={'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}} if cells['tile_telin'] else {};mp['tile_mechanics']=profiles
  for cell in cells['tile_fence']:assert cell['options']['passableMask']==2 and cell['options']['buildableType']==1
  stages[name]={'native_map_data':native['mapData'],'native_routes':native['routes'],'converted_map':mp,'converted_used_routes':routes,'actual_source_pairs':pairs,'all_special_tile_cells':cells,'native_options':native['options'],'native_runes':native['runes'],'runtime_stage_created':False}
 result={'schemaVersion':2,'manifest':{'id':'package/ch6/environment/source_consumer_v1','requires':['preset/ark_standard'],'metadata':{'source_before':locks,'source_after':{n:sha(Path(n)) for n in locks},'exact_environment_sources':s['prefabs'],'native_stages':stages,'tile_profiles':{'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}},'reference_policy':'All route positions/waits/offsets retained. Portals execute only source DISAPPEAR/APPEAR authored checkpoints, no inferred automatic teleport. Fence trueground-mask exclusion, FLY2 allowed, MELEE1 buildable; source emptyPrefab data0 is overlaid by exact native map operands, not fabricated passability.','method_body_policy':'Native Tile method bodies unavailable; existing explicit reference consumer preserved and separately probed','actual_geometry_verified':False,'whole_stage_executed':False,'client_verified':False}},'rules':[]};OUT.mkdir(parents=True,exist_ok=True);out=OUT/'module.reference.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(out),'stages':{n:{'fence':len(v['all_special_tile_cells']['tile_fence']),'pairs':len(v['actual_source_pairs'])} for n,v in stages.items()},'runtime':False}))
if __name__=='__main__':main()
