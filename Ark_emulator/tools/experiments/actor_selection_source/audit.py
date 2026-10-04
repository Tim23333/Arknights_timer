"""Offline source binding matrix. Missing getter fields stay unknown, never defaulted."""
from pathlib import Path
import json,hashlib,re
import UnityPy
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'packages/campaign/actor_selection_source/source.reference.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 sources={name:json.loads((ROOT/path).read_bytes()) for name,path in {'normalized':'packages/campaign/operators.normalized.json','attacks':'packages/campaign/attacks.reference.json','tokens':'packages/campaign/support_tokens.reference.json','emp':'packages/campaign/chapter01_devices/emp.source.json','enemies':'packages/campaign/chapter01_sources/native.reference.json','lock':'packages/campaign/operator_sources.lock.json'}.items()};locks={str(ROOT/path):sha(ROOT/path) for path in ['packages/campaign/operators.normalized.json','packages/campaign/attacks.reference.json','packages/campaign/support_tokens.reference.json','packages/campaign/chapter01_devices/emp.source.json','packages/campaign/chapter01_sources/native.reference.json','packages/campaign/operator_sources.lock.json']};table_path=ROOT/sources['lock']['files']['character_table.json']['path'];assert sha(table_path)==sources['lock']['files']['character_table.json']['sha256'];locks[str(table_path)]=sha(table_path);table=json.loads(table_path.read_bytes());cache={}
 def objects(record):
  path=ROOT.parent/record['path'];assert sha(path)==record['sha256'];locks[str(path)]=sha(path)
  if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
  return cache[path]
 script_record=next(iter(sources['enemies']['native_monoscripts'].values()))['source'];scripts=objects(script_record)
 def script_for(obj,raw,local):
  ptr=raw['m_Script']
  if ptr['m_FileID']==0:script=local[ptr['m_PathID']].read_typetree()
  else:
   expected=Path(script_record['path']).name;actual=str(obj.assets_file.externals[ptr['m_FileID']-1].path);assert actual.endswith('/'+expected);script=scripts[ptr['m_PathID']].read_typetree()
  return script
 current_dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=current_dump.read_text(encoding='utf8');locks[str(current_dump)]=sha(current_dump);enums={}
 for name in ['SideType','SideTypeIndex','EntityCategory','MotionMode','MotionMask','UnitType','UnitTypeMask','ProfessionCategory','AbnormalFlag','AbnormalCombo']:
  matches=list(re.finditer(r'public enum '+name+r' [^\n]*\n\{(.*?)\n\}',text,re.S));valid=[m for m in matches if (name!='UnitType' or 'public const UnitType TOKEN = 3;' in m[1])];assert len(valid)==1,(name,len(valid));m=valid[0];enums[name]={'values':{n:int(v) for n,v in re.findall(r'public const '+name+r' (\w+) = (-?\d+);',m[1])},'line':text[:m.start()].count('\n')+1,'declaration':m[0]}
 assert enums['UnitType']['values']['TOKEN']==3 and enums['UnitTypeMask']['values']['TOKEN']==4
 actors=[]
 def row(id,kind,raw,obj,script,character=None,version_pending=False):
  fields={k:raw[k] for k in ['_sideType','_sideTypeIndex','_category','_motionMode','_blockMode'] if k in raw};known={};unknown={}
  if '_category' in fields:assert type(fields['_category']) is int and fields['_category'] in enums['EntityCategory']['values'].values();known['category']={'value':fields['_category'],'source':'serialized _category literal'}
  else:unknown['category']='no serialized field; getter/initializer body not recovered'
  if '_motionMode' in fields:assert fields['_motionMode'] in (0,1);known['motion']={'value':1<<fields['_motionMode'],'native_motion_mode':fields['_motionMode'],'source':'serialized MotionMode plus explicit enum->mask encoding'}
  else:unknown['motion']='no serialized initial mode'
  if '_sideType' in fields and fields['_sideType'] in (1,2,4):known['side']={'value':{1:0,2:1,4:2}[fields['_sideType']],'native_side_mask':fields['_sideType'],'source':'serialized singleton SideType plus explicit SideTypeIndex encoding'}
  elif '_sideTypeIndex' in fields and type(fields['_sideTypeIndex']) is int and fields['_sideTypeIndex'] in (0,1,2):known['side']={'value':fields['_sideTypeIndex'],'source':'serialized absolute SideTypeIndex literal'}
  else:unknown['side']='no singleton serialized _sideType; initSideType/getter body not recovered'
  if character is not None:
   profession=character['profession'];assert profession in enums['ProfessionCategory']['values'];known['profession']={'value':enums['ProfessionCategory']['values'][profession],'native_profession':profession,'source':'actual character_table.profession; enum name mapping'}
  else:unknown['profession']='enemy has no character_table profession; NONE0 would be explicit model policy, not a serialized value'
  unknown['unit_type']='MonoScript class is evidence of implementation type, not a recovered unitType getter result; do not use token ID prefix or profession as getter proof'
  for key in ['target_free','ally_target_free','heal_free','camouflage','can_select_camouflage','target_free_flags','target_free_combos','abnormal_flags','abnormal_combos']:unknown[key]='runtime aggregate/body or live flag writers required; absent serialized root field is not a proven universal false'
  actors.append({'actor_id':id,'kind':kind,'actual_root_path_id':obj.path_id,'actual_serialized_file':str(obj.assets_file.name),'actual_native_class':script['m_ClassName'],'actual_monoscript':script,'actual_entity_fields':raw,'source_known_bindings':known,'unknown_bindings':unknown,'character_table_profession':character.get('profession') if character else None,'character_table_position':character.get('position') if character else None,'source_version_pending':version_pending,'runnable_actual_state':False})
 for operator in sources['normalized']['operators']:
  id=operator['character_id'];assert operator['raw_character']==table[id];a=next(x for x in sources['attacks']['operators'] if x['character_id']==id);local=objects(a['source']);obj=local[a['root_path_id']];raw=obj.read_typetree();row(id,'fixed12_character',raw,obj,script_for(obj,raw,local),table[id]);actors[-1]['prefab_source']=a['source']
 token_path=ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab';assert sha(token_path)==sources['tokens']['source']['sha256'];local={o.path_id:o for o in UnityPy.load(str(token_path)).objects};locks[str(token_path)]=sha(token_path)
 for id,t in sources['tokens']['tokens'].items():
  go=local[t['root_gameobject_path_id']].read_typetree();matches=[local[x['component']['m_PathID']] for x in go['m_Component'] if local[x['component']['m_PathID']].type.name=='MonoBehaviour' and local[x['component']['m_PathID']].read_typetree()==t['entity_fields']];assert len(matches)==1;obj=matches[0];raw=obj.read_typetree();row(id,'owned_token',raw,obj,script_for(obj,raw,local),table[id],True);actors[-1]['prefab_source']={'path':'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab','sha256':sha(token_path)}
 e=sources['emp'];local=objects(e['prefab']['source']);rows=[(pid,c) for pid,c in e['prefab']['components'].items() if c['native_class']=='MapDependentTrap'];assert len(rows)==1;pid,c=rows[0];obj=local[int(pid)];raw=obj.read_typetree();assert raw==c['raw'];row(e['level_config']['inst']['characterKey'],'native_EMP',raw,obj,script_for(obj,raw,local),e['character'],True);actors[-1]['prefab_source']=e['prefab']['source']
 for id in ['enemy_1014_rogue','enemy_1028_mocock','enemy_1028_mocock_2','enemy_1504_cqbw']:
  prefab=sources['enemies']['enemies'][id]['prefab'];local=objects(prefab['source']);rows=[(pid,c) for pid,c in prefab['components'].items() if c['native_class']=='Enemy'];assert len(rows)==1;pid,c=rows[0];obj=local[int(pid)];raw=obj.read_typetree();assert raw==c['raw'];row(id,'chapter01_enemy',raw,obj,script_for(obj,raw,local));actors[-1]['prefab_source']=prefab['source'];db=sources['enemies']['enemies'][id]['native_enemy'];defined=[r['enemyData']['motion']['m_value'] for r in db['raw_rows'] if r['enemyData']['motion']['m_defined']];assert defined and defined[-1]==db['resolved']['motion'];assert defined[-1] in ('WALK','FLY');actors[-1]['source_known_bindings']['motion']={'value':{'WALK':1,'FLY':2}[defined[-1]],'source':'native enemy DB explicit defined.motion inheritance','raw_rows':db['raw_rows'],'stage_override':db['stage_override']};actors[-1]['unknown_bindings'].pop('motion')
 flag_writers=[]; scanned_assets=set()
 for actor in actors:
  asset_key=actor['prefab_source']['sha256']
  if asset_key in scanned_assets:continue
  scanned_assets.add(asset_key)
  local=objects(actor['prefab_source'])
  for pid,obj in local.items():
   if obj.type.name!='MonoBehaviour':continue
   raw=obj.read_typetree()
   def scan(value,pointer=''):
    if isinstance(value,dict):
     for key,v in value.items():
      if key in ('abnormalFlags','abnormalCombos') and isinstance(v,list) and v:
       enum=enums['AbnormalFlag' if key=='abnormalFlags' else 'AbnormalCombo']['values'];assert all(type(x) is int and x in enum.values() and x!=enum['E_NUM'] for x in v)
       flag_writers.append({'associated_source_roots':[a['actor_id'] for a in actors if a['prefab_source']['sha256']==asset_key],'source':actor['prefab_source'],'component':pid,'pointer':pointer+'/'+key,'indices':v,'names':[next(n for n,x in enum.items() if x==i) for i in v],'scope':'whole asset inventory only; actor reachability, selected mode and runtime trigger/lifetime NOT established; not a bound live status writer'})
      scan(v,pointer+'/'+key)
    elif isinstance(value,list):
     for i,v in enumerate(value):scan(v,pointer+'/'+str(i))
   scan(raw)
 audit=ROOT/'validation/campaign/advanced_selector_source_audit.json';selector=json.loads(audit.read_bytes());locks[str(audit)]=sha(audit)
 result={'schema':'ark-sim/actor-selection-source-bindings/v1','offline_source_checks_passed':True,'client_verified':False,'source_locks':locks,'current_dump_enums':enums,'actors':actors,'native_flag_field_inventory_not_bound_writers':flag_writers,'native_selector_source':selector['actual_selectors'],'defaults_used':False,'generator_plan':'sparse source_known_bindings only; unknown consumption must require explicit model profile or captured/native proof before complete actual-state wrapper','important_distinctions':['Cannon and EMP category2 vs Mon category1','Bird uses Character native class, not Token, and lacks serialized side/category','MELEE/RANGED is placement position, not native motion enum','UnitType TOKEN3 is not UnitTypeMask TOKEN4','Profession TOKEN128 is independent of category and unit type','actor initial flags do not prove live runtime aggregates or disabled selector fields'],'formal_approval':False}
 assert all(sha(Path(p))==pin for p,pin in locks.items());OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'actors':len(actors),'defaults_used':False,'sha256':sha(OUT)}))
if __name__=='__main__':main()
