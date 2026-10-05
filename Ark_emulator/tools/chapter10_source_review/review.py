"""Independent four-gate, type-exact chapter10 source audit; no runtime imports."""
import json,hashlib,traceback
from copy import deepcopy
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PLAN=ROOT/'packages/campaign/chapter10_source_prepare/source.plan.v1.json'
OUT=ROOT/'validation/campaign/chapter10_source_review'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
plan=load(PLAN)
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
def guard():return {str(PLAN):sha(PLAN),**{k:sha(Path(k)) for k in plan['source_locks']}}
BEFORE=guard();facts={};results=[]
def pinned_lossless():
 assert all(BEFORE[k]==h for k,h in plan['source_locks'].items())
 assert plan['fixed_commit']=='56aee3d6c5a29c3a0d192456d70d14252cbb0804'
 rows=[]
 for level,s in plan['stages'].items():
  path=ROOT/'packages/campaign/native_reference'/(level+'.json');n=load(path)
  assert exact(s['native_document'],n)
  assert s['asset_identity']['sha256']==sha(path)
  assert s['native_document_digest']==hashlib.sha256(json.dumps(n,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
  assert exact(s['options'],n['options'])
  assert not s['runtime_created'] and not s['simulation_passed']
  rows.append({'level':level,'native_LevelData_sha256':sha(path),'whole_document_type_exact':True})
 assert len(rows)==2;facts['pinned_lossless']=rows

def actions_tokens():
 expected={'level_main_10-14':(32,10,0),'level_main_10-15':(67,15,1)};rows=[]
 for level,s in plan['stages'].items():
  n=s['native_document'];birth,dp,pot=expected[level];flat=[];counts=Counter();controls=Counter()
  for wi,w in enumerate(n['waves']):
   for fi,f in enumerate(w['fragments']):
    for ai,a in enumerate(f['actions']):
     flat.append((wi,fi,ai,a))
     assert type(a['count']) is int
     (counts if a['actionType']=='SPAWN' else controls)[a['key'] if a['actionType']=='SPAWN' else a['actionType']]+=a['count']
  assert len(flat)==len(s['actions'])==30
  for (wi,fi,ai,a),r in zip(flat,s['actions']):
   assert (wi,fi,ai)==(r['wave'],r['fragment'],r['action']) and exact(a,r['native'])
   if a['actionType']=='SPAWN':
    v=plan['variants'][r['variant_id']];assert a['key']==v['native_enemy']['native_id'] and type(a['routeIndex']) is int and 0<=a['routeIndex']<30
  assert sum(counts.values())==birth==s['features']['spawn_count'];assert dict(counts)==s['features']['spawn_by_key']
  assert n['options']['initialCost']==dp and n['options']['characterLimit']==8 and n['options']['maxLifePoint']==3
  tokens=[{'bucket':k,'index':i,'native_record':x} for k,v in n['predefines'].items() for i,x in enumerate(v or [])];assert exact(tokens,s['predefine_records'])
  token=n['predefines']['tokenInsts'][0];assert token['inst']['characterKey']=='trap_058_gunctrl' and token['inst']['level']==1 and token['inst']['potentialRank']==pot
  assert token['hidden'] is False and token['direction']=='UP' and exact(token['position'],{'row':0,'col':0})
  rows.append({'level':level,'births':birth,'wave_action_records':len(flat),'control_counts':dict(controls),'DP':dp,'slots':8,'source_life':3,'token058':token,'hardPredefines_type_preserved':True})
 assert len(plan['variants'])==len(plan['dependency_matrix'])==14;facts['actions_tokens']=rows

def override_semantics():
 db=load(next(Path(k) for k in plan['source_locks'] if k.endswith('enemy_database.json')))
 def layer(dst,src):
  out=deepcopy(dst)
  for key,value in src.items():
   if isinstance(value,dict) and 'm_defined' in value:
    assert type(value['m_defined']) is bool and 'm_value' in value
    if value['m_defined'] is True:out[key]=deepcopy(value['m_value'])
   elif isinstance(value,dict):out[key]=layer(out.get(key,{}),value)
   elif value is not None:out[key]=deepcopy(value)
  return out
 rows=[]
 for vid,v in plan['variants'].items():
  ref=v['native_reference'];enemy=v['native_enemy'];selected=sorted((r for r in db[ref['id']] if r['level']<=ref['level']),key=lambda r:r['level'])
  assert selected[-1]['level']==ref['level'] and exact(selected,enemy['raw_rows']) and exact(ref.get('overwrittenData'),enemy['stage_override'])
  resolved={}
  for r in selected:resolved=layer(resolved,r['enemyData'])
  resolved=layer(resolved,ref.get('overwrittenData') or {})
  assert exact(resolved,enemy['resolved'])
  rows.append({'variant_id':vid,'source_HP':resolved['attributes']['maxHp'],'resolved_type_exact':True})
 boss=next(v for v in plan['variants'].values() if v['native_enemy']['native_id']=='enemy_1528_manfri');o=boss['native_reference']['overwrittenData'];r=boss['native_enemy']['resolved']
 assert o['attributes']['maxHp']=={'m_defined':False,'m_value':0} and r['attributes']['maxHp']==40000
 assert o['attributes']['silenceImmune']=={'m_defined':False,'m_value':False} and r['attributes']['silenceImmune'] is True
 assert exact(layer({'a':7,'b':True,'c':9},{'a':{'m_defined':True,'m_value':0},'b':{'m_defined':True,'m_value':False},'c':{'m_defined':False,'m_value':0}}),{'a':0,'b':False,'c':9})
 facts['override_semantics']={'variants':rows,'undefined_false_zero_does_not_override':True,'defined_zero_false_does_override':True,'boss_HP40000_DEF600_RES40_LP2':r['attributes']['maxHp']==40000 and r['attributes']['def']==600 and r['attributes']['magicResistance']==40.0 and r['lifePointReduce']==2}

def geometry():
 rows=[];build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passing={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3}
 for level,s in plan['stages'].items():
  n=s['native_document'];grid=n['mapData']['map'];palette=n['mapData']['tiles'];R=len(grid);C=len(grid[0]);tiles=[]
  for row in grid:
   assert len(row)==C
   for index in row:
    assert type(index) is int and 0<=index<len(palette);t=palette[index];tiles.append({'tileKey':t['tileKey'],'buildableType':build[t['buildableType']],'passableMask':passing[t['passableMask']],'heightType':t['heightType'],'blackboard':deepcopy(t.get('blackboard')),'effects':deepcopy(t.get('effects'))})
  assert exact(tiles,s['map_plan']['tiles']) and (R,C)==(s['map_plan']['rows'],s['map_plan']['cols']);assert s['map_plan']['coordinate_conversion']=='map rows are top-down; native route row -> rows-1-row'
  assert len(n['routes'])==30;nonzero=sum(any(r['startPosition'].values()) or any(r['endPosition'].values()) for r in n['routes']);assert nonzero==s['features']['nonzero_endpoint_routes']
  cp=Counter();tele=[]
  for ri,r in enumerate(n['routes']):
   for ci,c in enumerate(r.get('checkpoints') or []):
    cp[c['type']]+=1
    if c['type'] in ['DISAPPEAR','APPEAR_AT_POS']:tele.append({'route':ri,'checkpoint':ci,'native':c})
  assert cp['DISAPPEAR']==cp['APPEAR_AT_POS']==(8 if level.endswith('14') else 7)
  rows.append({'level':level,'rows':R,'cols':C,'routes':30,'nonzero_endpoint_routes':nonzero,'checkpoint_counts':dict(cp),'teleport_source_checkpoints':tele,'native_route0_start':n['routes'][0]['startPosition'],'future_topdown_route0_start':{'row':R-1-n['routes'][0]['startPosition']['row'],'col':n['routes'][0]['startPosition']['col']},'coordinate_conversion_not_applied_to_raw_document':True})
 facts['geometry']=rows
for name,fn in [('pinned_full_document_lossless',pinned_lossless),('birth_action_token_options_exact',actions_tokens),('all14_variants_defined_value_semantics',override_semantics),('map_route_teleport_lossless',geometry)]:
 try:fn();results.append({'gate':name,'passed':True})
 except Exception:results.append({'gate':name,'passed':False,'traceback':traceback.format_exc()})
AFTER=guard();code=0 if all(r['passed'] for r in results) and BEFORE==AFTER else 1
report={'schema':'chapter10-independent-source-review/v1','actual_exit':code,'plan_path':str(PLAN),'plan_sha256':sha(PLAN),'helper_sha256':sha(Path(__file__)),'source_before':BEFORE,'source_after':AFTER,'source_guard_equal':BEFORE==AFTER,'results':results,'facts':facts,'count_correction':'Native has 30 actions per stage and 30 DISAPPEAR/APPEAR_AT_POS checkpoint records in total; 37 is not supported by these two assets.','required_consumers_and_gaps':plan['required_consumers_and_gaps'],'runtime_created':False,'simulation_started':False,'whole_stage_executed':False,'client_verified':False,'source_inputs_are_not_logs':True}
OUT.mkdir(parents=True,exist_ok=True);p=OUT/'source.review.v1.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results,'receipt_sha256':sha(p),'plan_sha256':sha(PLAN)}));raise SystemExit(code)
