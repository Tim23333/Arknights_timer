"""Read-only 43/7/portal dependency receipt, awaiting frozen Ice/arbiter join."""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter04_10_join_prepare'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 planpath=ROOT/'packages/campaign/chapter04_plans/source.plan.json';assert sha(planpath)=='2b9a49412d64945eacca82282866b4c8b12eb11f5676dd831878a51ec01a9086';plan=json.loads(planpath.read_bytes());stage=plan['stages']['level_main_04-10'];native=stage['native_document'];assert stage['spawn_count']==43 and len(stage['variant_ids'])==7
 candidates=[ROOT/'packages/campaign/chapter04_units/ordinary.reference_model.json',ROOT/'packages/campaign/chapter04_units/ranged/combat_guard.source_circle.reference_model.json',ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'];modules={};bindings=[]
 for path in candidates:
  p=json.loads(path.read_bytes());byvariant={}
  for section in ('definitions','entities'):
   for d in p.get(section,[]):
    vid=d.get('metadata',{}).get('native_variant_id',d.get('metadata',{}).get('native_variant'))
    if d.get('kind')=='entity' and vid:byvariant[vid]=d['id']
  modules[str(path.relative_to(ROOT))]={'sha256':sha(path),'exact_entity_bindings':byvariant}
 for vid in stage['variant_ids']:
  matches=[{'module':path,'entity':m['exact_entity_bindings'][vid]} for path,m in modules.items() if vid in m['exact_entity_bindings']]
  assert len(matches)<=1;bindings.append({'variant':vid,'native_reference':plan['variants'][vid]['native_reference'],'available_exact_match':matches,'pending':'Frozen full Frost normal/rebirth/three-skill/Ice/arbiter composition' if not matches else None})
 portalpath=ROOT/'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json';assert sha(portalpath)=='a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1';portal=json.loads(portalpath.read_bytes())['scenarioDraft']['map']['tile_mechanics'];profiles={k:portal[k] for k in ('tile_telin','tile_telout')};assert profiles=={'tile_telin':{'type':'route_checkpoint_portal','role':'entry'},'tile_telout':{'type':'route_checkpoint_portal','role':'exit'}}
 route_records=[]
 for ri in stage['used_routes']:
  r=native['routes'][ri]
  for ci,c in enumerate(r.get('checkpoints') or []):
   if c.get('type') in ('DISAPPEAR','APPEAR_AT_POS'):route_records.append({'route_index':ri,'checkpoint_index':ci,'native':c,'runtime_cell':{'row':stage['map_plan']['rows']-1-c['position']['row'],'col':c['position']['col']} if c.get('position') else None})
 cells=[{'cell':{'row':i//stage['map_plan']['cols'],'col':i%stage['map_plan']['cols']},'tile':t} for i,t in enumerate(stage['map_plan']['tiles']) if t['tileKey'] in profiles]
 watched=[planpath,portalpath,*candidates,ROOT/'tools/build_reference_stage_scenario_v2.py',ROOT/'tools/campaign_content_composition.py',ROOT/'ark_sim/domains/tile_mechanics.py',ROOT/'ark_sim/domains/movement.py',Path(__file__)];before={str(p):sha(p) for p in watched};after={str(p):sha(p) for p in watched};assert before==after
 report={'scope':'Read-only actual 4-10 source dependencies; not a stage/core construction or Ice edit','births':43,'exact_variants':7,'variant_bindings':bindings,'native_seed':native['randomSeed'],'native_options':native['options'],'source_map_dimensions':[stage['map_plan']['rows'],stage['map_plan']['cols']],'native_checkpoint_counts':stage['used_checkpoint_counts'],'portal_profiles':profiles,'portal_profile_source':str(portalpath),'portal_profile_sha256':sha(portalpath),'portal_cells':cells,'native_route_portal_checkpoints':route_records,'available_modules':modules,'required_pending':['Frozen full Frost three-skill priority arbiter + normal/rebirth/immunity + Ice/tile denial source module, no truncated/stale normal-only substitute','Root accepted tile peer and exact content/runtime SHA','Fresh runtime guard, composition union and required definition contract bindings','Exact born43/ref7 accounting, life99999 base only, fixed12 roster with native10 deployment slots, native seed and whole source timeline unchanged','Real portal checkpoint/path visibility/CP/replay consumers, complete standalone source cases before a full-stage receipt'],'guards_before':before,'guards_after':after,'whole_stage_executed':False,'client_verified':False}
 OUT.mkdir(parents=True,exist_ok=True);dest=OUT/'dependencies.json'
 if dest.exists():raise ValueError('Preserve earlier dependency receipt')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'report_sha':sha(dest),'available_nonboss_variants':sum(bool(r['available_exact_match']) for r in bindings),'portal_checkpoints':len(route_records),'native_slots':native['options']['characterLimit']}))
if __name__=='__main__':main()
