"""Independent raw source audit and bounded FrostNova dependency plan, no runtime."""
import argparse,json,hashlib,base64,re,sys,struct,math
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];PLAN=ROOT/'packages/campaign/chapter04_plans/source.plan.json';SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json';OUT=ROOT/'packages/campaign/chapter04_boss_plan/source.reference.json'
sys.path.insert(0,str(ROOT))
PINS={PLAN:'2b9a49412d64945eacca82282866b4c8b12eb11f5676dd831878a51ec01a9086',SOURCE:'3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bson_document(raw,start=0,array=False):
 size=struct.unpack_from('<i',raw,start)[0];end=start+size
 if size<5 or end>len(raw) or raw[end-1]!=0:raise ValueError('BSON document bounds')
 offset=start+4;value={}
 while offset<end-1:
  kind=raw[offset];offset+=1;zero=raw.index(0,offset,end);key=raw[offset:zero].decode('utf8');offset=zero+1
  if key in value:raise ValueError('duplicate BSON key')
  if kind==1:item=struct.unpack_from('<d',raw,offset)[0];offset+=8;assert math.isfinite(item)
  elif kind==2:
   length=struct.unpack_from('<i',raw,offset)[0];offset+=4
   if length<1 or offset+length>end or raw[offset+length-1]!=0:raise ValueError('BSON string bounds')
   item=raw[offset:offset+length-1].decode('utf8');offset+=length
  elif kind in (3,4):item,offset=bson_document(raw,offset,kind==4)
  elif kind==8:
   if raw[offset] not in (0,1):raise ValueError('BSON bool')
   item=bool(raw[offset]);offset+=1
  elif kind==10:item=None
  elif kind in (16,18):item=struct.unpack_from('<i' if kind==16 else '<q',raw,offset)[0];offset+=4 if kind==16 else 8
  else:raise ValueError('Unsupported BSON source tag:'+str(kind))
  if offset>end-1:raise ValueError('BSON element outside document')
  value[key]=item
 if offset!=end-1:raise ValueError('BSON terminator position')
 if array:
  if list(value)!=[str(i) for i in range(len(value))]:raise ValueError('BSON array index order')
  value=list(value.values())
 return value,end
def build():
 from tools.build_chapter01_enemy_sources import NativeAssets
 from tools.extract_campaign_animation_bindings import resolve_animation
 for p,pin in PINS.items():
  if sha(p)!=pin:raise ValueError('Frozen C4 source changed:'+str(p))
 plan=json.loads(PLAN.read_bytes());source=json.loads(SOURCE.read_bytes());locks={str(p.relative_to(ROOT.parent)).replace('\\','/'):sha(p) for p in PINS};checks=[]
 for collection in (plan['source_locks'],source['source_locks']):
  for name,pin in collection.items():
   if sha(ROOT.parent/name)!=pin:raise ValueError('Source lock stale:'+name)
   locks[name]=pin
 masks={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3,'WALK_ONLY':1,'FLY_ONLY':2};stages={}
 for name,stage in plan['stages'].items():
  path=ROOT/'packages/campaign/native_reference'/(name+'.json');native=json.loads(path.read_bytes());assert native==stage['native_document'];flat=[];pop=Counter();controls=Counter();used=set();rows=[]
  for row in native['mapData']['map']:
   for index in row:
    tile=native['mapData']['tiles'][index];flat.append({'tileKey':tile['tileKey'],'buildableType':masks[tile['buildableType']],'passableMask':masks[tile['passableMask']],'heightType':tile['heightType'],'blackboard':tile.get('blackboard'),'effects':tile.get('effects')})
  assert flat==stage['map_plan']['tiles'] and stage['map_plan']['rows']==len(native['mapData']['map']) and stage['map_plan']['cols']==len(native['mapData']['map'][0])
  for wi,w in enumerate(native['waves']):
   for fi,f in enumerate(w['fragments']):
    for ai,action in enumerate(f['actions']):
     rows.append((wi,fi,ai,action))
     if action['actionType']=='SPAWN':pop[action['key']]+=action['count'];used.add(action['routeIndex'])
     else:controls[action['actionType']]+=action['count']
  assert sum(pop.values())==stage['spawn_count'] and dict(pop)==stage['spawn_by_key'] and dict(controls)==stage['control_count_by_type'] and sorted(used)==stage['used_routes']
  assert [(r['wave'],r['fragment'],r['action'],r['native']) for r in stage['actions']]==rows
  assert stage['normal_runes']['raw']==native['runes'] and stage['normal_runes']['mask']==1 and all(not v for v in native['predefines'].values())
  stages[name]={'native_path':str(path.relative_to(ROOT)),'sha256':sha(path),'births':sum(pop.values()),'variants':stage['variant_ids'],'used_routes':sorted(used),'control_counts':dict(controls),'map_cells':len(flat),'native_options_preserved':True,'native_predefines_preserved':True,'native_runes_preserved':True};checks.append({'scope':name,'claim':'raw native document, independent flatten masks, full wave/action counts/flags/indices/routes/runes/predefines equal'})
 assert len(source['variants'])==13 and [stages[k]['births'] for k in sorted(stages)]==[49,43]
 assets=NativeAssets();actual={}
 for category in ('prefabs','projectiles'):
  for key,stored in source[category].items():
   path=ROOT.parent/stored['source']['path'];closure=assets.closure(path,key)
   assert {k:(v['native_class'],v['raw']) for k,v in closure['components'].items()}=={k:(v['native_class'],v['raw']) for k,v in stored['components'].items()}
   assert closure['root_gameobject_path_id']==stored['root_gameobject_path_id'];actual[key]=closure
   checks.append({'scope':category+'/'+key,'claim':'fresh exact GameObject/subtree component PPtr, raw typetrees and MonoScript class equality','path':stored['source']['path'],'sha256':sha(path),'components':len(closure['components'])})
 # Source BSON document bytes are read independently from its frozen offset.
 bson=source['bson_templates'];wrapper=(ROOT.parent/bson['source']['path']).read_bytes();name_length=struct.unpack_from('<i',wrapper,0)[0];header=(4+name_length+3)&~3;length=struct.unpack_from('<i',wrapper,header)[0]
 assert name_length>=0 and length>=0 and header+4+length<=len(wrapper);data=wrapper[header+4:header+4+length];assert hashlib.sha256(data).hexdigest()==bson['payload_sha256']
 for key,record in bson['templates'].items():
  raw=base64.b64decode(record['document_base64']);assert data[record['payload_offset']:record['payload_offset']+len(raw)]==raw and hashlib.sha256(raw).hexdigest()==record['document_sha256'];decoded,end=bson_document(raw);assert end==len(raw) and decoded==record['parsed']
  checks.append({'scope':'BSON/'+key,'claim':'actual byte offset and independent BSON decoding equality','document_sha256':record['document_sha256']})
 projectile_bb=[]
 for key,prefab in actual.items():
  def walk(value,path=''):
   if isinstance(value,dict):
    if value.get('key')=='projectile' and value.get('valueStr'):
     assert value['valueStr'] in actual;projectile_bb.append({'prefab':key,'path':path,'raw':value,'dependency':value['valueStr']})
    for k,v in value.items():walk(v,path+'/'+k)
   elif isinstance(value,list):
    for i,v in enumerate(value):walk(v,path+'/'+str(i))
  walk(prefab['components'])
 assert any(r['dependency']=='projectile_bslime' for r in projectile_bb)
 demon=next(v for v in source['variants'].values() if v['prefab_key']=='enemy_1010_demon');drivers=[]
 for d in demon['additional_animation_drivers']:
  assert actual[demon['prefab_key']]['components'][str(d['path_id'])]['raw']==d['raw']
  for field,binding in d['bindings'].items():assert resolve_animation(d['raw'][field],source['animations'][demon['prefab_key']]['animator']['fields']['_animations'],source['animations'][demon['prefab_key']]['parsed'])==binding
  drivers.append(d)
 assert [e['frame'] for e in drivers[0]['bindings']['_animWithPre']['events']]==[27] and [e['frame'] for e in drivers[0]['bindings']['_animNoPre']['events']]==[15]
 boss=source['variants']['enemy_1505_frstar@0/9d1e3d01ef79ae3e'];components=actual[boss['prefab_key']]['components'];selected={pid:c for pid,c in components.items() if c['native_class'] in ['RebornTalent','EnemySkill','SpawnTokenOnTileAbility','TileSelector','TileTrigger','PassiveBuffAbility','RangedAttack','AdvancedSelector','CircleRange']}
 token_path=ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab';token=assets.closure(token_path,'trap_004_iceblock');locks[str(token_path.relative_to(ROOT.parent)).replace('\\','/')]=sha(token_path)
 table_path=ROOT.parent/'unpack_work/campaign_tables/character_table.json';table=json.loads(table_path.read_bytes());locks[str(table_path.relative_to(ROOT.parent)).replace('\\','/')]=sha(table_path)
 dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=dump.read_text(encoding='utf8');locks[str(dump.relative_to(ROOT.parent)).replace('\\','/')]=sha(dump)
 enums={}
 for name in ['SideType','SideTypeIndex','TileSelector.FilterType','AttributeType','AttributeModifierData.AttributeModifier.FormulaItemType','Entity.MountPointType']:
  match=re.search(r'public enum '+re.escape(name)+r'[^\n]*\n\{(.*?)\n\}',text,re.S);assert match;enums[name]={'declaration':match.group(0),'methods_recovered':False}
 reborn=next(c['raw'] for c in components.values() if c['native_class']=='RebornTalent');assert (reborn['_maxRespawnCnt'],reborn['_hpRechargeRatio'])==(1,.5)
 skill_nodes={c['gameobject_name']:c for c in components.values() if c['native_class']=='EnemySkill'};assert set(skill_nodes)=={'ArcticBlast','IceShield'}
 by_go={}
 for pid,c in components.items():by_go.setdefault(c['raw']['m_GameObject']['m_PathID'],[]).append(c)
 blast_go=skill_nodes['ArcticBlast']['raw']['m_GameObject']['m_PathID'];blast=next(c for c in by_go[blast_go] if c['native_class']=='RangedAttack');assert blast['raw']['_waitForAttackEvent']==0 and blast['raw']['_preDelay']==.9330000281333923 and blast['raw']['_damageType']==2
 token_go=skill_nodes['IceShield']['raw']['m_GameObject']['m_PathID'];spawn=next(c for c in by_go[token_go] if c['native_class']=='SpawnTokenOnTileAbility');assert spawn['raw']['_tokenToSpawn']['inst']['characterKey']=='trap_004_iceblock' and spawn['raw']['_tokenToSpawn']['inst']['level']==0
 binding=resolve_animation(spawn['raw']['_animKey'],source['animations'][boss['prefab_key']]['animator']['fields']['_animations'],source['animations'][boss['prefab_key']]['parsed']);assert [e['frame'] for e in binding['events'] if e['name']=='OnAttack']==[55]
 assert boss['native_enemy']['resolved']['attributes']['maxHp']==25000 and boss['native_enemy']['resolved']['attributes']['atk']==420
 root=next(c['raw'] for c in token['components'].values() if c['native_class']=='Trap');assert root['_category']==2 and root['_sideType']==1 and root['_rewriteTileOptions']==0
 plan_data={'rebirth':{'source_delay_seconds':5,'source_max_count':1,'raw_hp_ratio':.5,'reference_hp_ratio':1,'declared_profile':'reference_full_capacity','attack_bonus_ratio':.5,'source_sleep_immunity_combo':0,'after_rebirth_sleep_immunity_removed':True,'source_conflict':'serialized hpRechargeRatio.5 vs reference100%; actual loader body not recovered'},
 'arctic_blast':{'source_skill_key':'ArcticBlast','initial_cd':8.5,'cd':8.5,'priority':1,'atk_scale':1.5,'trigger_radius':2.5,'splash_radius':2,'attack_speed_points':-50,'selected_duration_seconds':8,'raw_buff_lifetime_seconds':4,'effect_windup_raw_seconds':.9330000281333923,'source_event_wait':False,'raw_normal_attack_events':[17,28],'declared_normal_packet':'first OnAttack17 only; second28 matches separate skill preDelay, not automatic two-packet proof','source_skill_ground_only_trigger':True,'reference_ground_only_hit':True,'source_hit_motion3_vs_reference_no_air_conflict':True},
 'ice_shield':{'initial_cd':30,'cd':30,'priority':2,'source_tile_count':2,'source_spawn_frame':55,'source_tile_filter':2,'source_filter_enum':'EXCEPT_CHARACTER','declared_profile':'reference deployment-eligible cells in radius2, choose min(2,n) uniformly without replacement, do not infer native RNG stream/algorithm','instant_kill_uses_damage_packet':False,'instant_kill_skip_reborn_raw':False,'token_character_config_source_level':0,'character_table_entry_present':'trap_004_iceblock' in table,'source_no_hit_colliders':True,'source_no_terrain_rewrite':True,'declared_token':'reference HP100/ATK0/DEF0/RES0, own cell occupancy, no hitbox, persistent source-retire retain, no ground-wall rewrite'},
 'required_generic_extensions':['delayed first health/instant-kill down→same actor recovery; World persistent count/owned task, managed population retained; no first-down combat.kill','inactive down-phase prevents movement/attack/block/selection/resources; no fake HP1','full-capacity restore, source ATK+.5 and old sleep-immunity cleanup; second true death','enemy skill clock and priority arbiter, cooldown pause/reset after rebirth; policy explicit where body unknown','pure tile eligibility/query and RNG-backed tile selection at accepted cast; no query draws','instant kill cause/source/rebirth policy without fake damage; nonpaid token placement with deploy cell occupancy and no hitbox targeting']}
 locks[str(Path(__file__).relative_to(ROOT.parent)).replace('\\','/')]=sha(Path(__file__))
 return {'schema':'ark-sim/chapter04-boss-source-plan/v1','status':'independent_raw_audit_and_reference_dependency_plan','source_locks':locks,'source_checks':checks,'stages':stages,'exact_variant':boss['variant_id'],'native_enemy':boss['native_enemy'],'boss_components':selected,'boss_modes':boss['modes'],'boss_animation':source['animations'][boss['prefab_key']],'boss_projectiles':{k:v for k,v in source['projectiles'].items() if 'frstar' in k},'valueStr_projectile_dependencies':projectile_bb,'demon_both_animation_branches':drivers,'sealed_floor_native':token,'enums':enums,'reference_sources':[{'url':'https://prts.wiki/w/%E9%9C%9C%E6%98%9F','checked_date':'2026-10-03','claims':['L0 stats25000/420/250/50','first down5s, full HP restore, ATK+50%, lose sleep immunity','blast150% arts,8s AS-50,ground only; freeze2 deployment cells/force knockout']},{'url':'https://prts.wiki/w/%E5%B0%81%E5%8D%B0%E7%9A%84%E5%9C%B0%E9%9D%A2','checked_date':'2026-10-03','claims':['HP100, no hitbox, no terrain rewrite; occupancy forbids deployment; not manually withdrawable']}],'declared_plan':plan_data,'runtime_created':False,'client_verified':False,'formal_approved':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(exist_ok=True)
 if a.check:
  if OUT.read_bytes()!=raw:raise ValueError('C4 boss audit stale')
 else:OUT.write_bytes(raw)
 print(json.dumps({'sha256':sha(OUT),'checks':len(p['source_checks']),'stages':{k:v['births'] for k,v in p['stages'].items()},'runtime':False}))
