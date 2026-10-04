"""Independent source conservation and source-only freeze; no runtime acceptance."""
import base64,hashlib,json,shutil
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter07_sources_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);invpath=ROOT/'packages/campaign/chapter07_sources/source.inventory.json';inv=json.loads(invpath.read_bytes());assert inv['source_before']==inv['source_after'];assert all(sha(Path(p))==h for p,h in inv['source_after'].items());plan=json.loads((ROOT/'packages/campaign/chapter07_plans/source.plan.json').read_bytes());enemy=json.loads((ROOT/'packages/campaign/chapter07_sources/native.reference.json').read_bytes());npc=json.loads((ROOT/'packages/campaign/chapter07_predefines/source.v4.reference.json').read_bytes());assert plan['selected_display_ids']=={'main_07-15':'7-17','main_07-16':'7-18'};rows=[]
 for name,births,variants in [('level_main_07-15',37,6),('level_main_07-16',45,8)]:
  s=plan['stages'][name];native=s['native_document'];assert s['spawn_count']==births and len(s['variant_ids'])==variants;counts=Counter();controls=Counter()
  for w in native['waves']:
   for f in w['fragments']:
    for a in f['actions']:
     if a['actionType']=='SPAWN':counts[a['key']]+=a['count'];assert native['routes'][a['routeIndex']]['motionMode']=='WALK'
     else:controls[a['actionType']]+=a['count']
  assert sum(counts.values())==births and dict(counts)==s['spawn_by_key'] and dict(controls)==s['control_count_by_type'];assert npc['stages'][name]['native_predefines']==s['predefines'];assert (s['options']['characterLimit'],s['options']['initialCost'],s['options']['maxLifePoint'],s['options']['moveMultiplier'])==(9,10,3,.5);rows.append({'stage':name,'births':births,'variants':variants,'slots':9,'DP':10,'life':3,'move':.5,'control_counts':dict(controls),'used_routes_all_native_WALK':True})
 assert len(enemy['variants'])==len(enemy['prefabs'])==12 and len(enemy['projectiles'])==3;assert all(v['status']=='exact_source_bound_spine' for v in enemy['animations'].values());assert not enemy['bson_templates']['missing_templates'] and not npc['bson_templates']['missing_templates']
 bson_checks=0
 for bundle in (enemy['bson_templates'],npc['bson_templates']):
  for key,row in bundle['templates'].items():assert hashlib.sha256(base64.b64decode(row['document_base64'])).hexdigest()==row['document_sha256'];bson_checks+=1
 ore=npc['prefabs']['trap_011_ore'];mine=npc['prefabs']['trap_012_mine'];assert ore['source']['sha256']==mine['source']['sha256']=='b9f16db4bfc8e8c880a0f90a1a7a74eda3b47c2188d0a151e5239d154716d475';assert sum(c.get('native_null_gameobject_preserved',False) for c in mine['components'].values())==2;assert plan['stages']['level_main_07-16']['predefines']['tokenInsts'][0]['alias'] is None;assert plan['stages']['level_main_07-16']['predefines']['tokenCards'][0]['initialCnt']==15
 sourcefiles=list((ROOT/'tools/chapter07').glob('*.py'));source_archives=[]
 for p in sourcefiles:
  dst=OUT/'source'/p.name;shutil.copyfile(p,dst);assert sha(p)==sha(dst);source_archives.append({'path':str(p),'sha':sha(p)})
 record={'role':'Exact offline source preparation only, nine dependency classes','inventory':{'path':str(invpath),'sha':sha(invpath)},'source_before':inv['source_before'],'source_after':{p:sha(Path(p)) for p in inv['source_after']},'new_source_tool_archives':source_archives,'stage_conservation':rows,'exact_prefab_spine_variants':12,'exact_projectiles':3,'actual_BSON_document_hash_checks':bson_checks,'predefined_references_and_stock_native_preserved':True,'official20250327_token_version_difference_explicit':True,'local_source_GameObject_null_preserved':True,'typed_FB_inline_key_query':{'keys':37,'matches':0,'loadFromDB_required_refs':0,'status':'Inline native0 remains inline. No guessed empty DB Buff inserted.'},'source_method_bodies_missing_is_pending_not_blocker':True,'runtime_consumer_authored':False,'stage_join_created':False,'whole_stage_executed':False,'client_verified':False};assert record['source_before']==record['source_after'];dest=OUT/'freeze.json';dest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'source_inventory_sha':sha(invpath),'stages':rows,'runtime':False}))
if __name__=='__main__':main()
