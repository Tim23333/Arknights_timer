"""Local exact source conflict proof; no choice of native HP threshold."""
import json,hashlib,argparse,base64,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json';OUT=ROOT/'packages/campaign/chapter02_behavior/skulsr.conflict.reference.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def declaration(text,name):
 match=re.search(r'^(?:public|private|protected|internal).*\b(?:class|enum|struct) '+re.escape(name)+r'(?:\s|[:/])',text,re.M)
 if not match:raise ValueError('exact declaration absent: '+name)
 end=text.find('\n// Namespace:',match.end());end=len(text) if end<0 else end
 return {'line':text[:match.start()].count('\n')+1,'text':text[match.start():end],'methods_are_signatures_only':True}
def build():
 import UnityPy
 d=json.loads(SOURCE.read_bytes());variant=next(r for r in d['variants'].values() if r['native_enemy']['native_id']=='enemy_1500_skulsr');prefab=d['prefabs'][variant['prefab_key']];path=ROOT.parent/prefab['source']['path'];assert sha(path)==prefab['source']['sha256'];objects={o.path_id:o for o in UnityPy.load(str(path)).objects}
 for pid,c in prefab['components'].items():assert objects[int(pid)].read_typetree()==c['raw']
 projectile=d['projectiles']['projectile_skulsr'];asset=ROOT.parent/projectile['source']['path'];assert sha(asset)==projectile['source']['sha256'];objects={o.path_id:o for o in UnityPy.load(str(asset)).objects}
 for pid,c in projectile['components'].items():assert objects[int(pid)].read_typetree()==c['raw']
 checker=next({'path_id':pid,**c} for pid,c in prefab['components'].items() if c['native_class']=='HpRatioToggleChecker');bb={x['key']:x['value'] for x in variant['native_enemy']['resolved']['talentBlackboard']}
 assert checker['raw']['_maxHpRatio']==0.4000000059604645 and bb['atkup.hp_ratio']==.5 and checker['raw']['_loadMinHpRatioFromBlackboard']==0
 dumps={};locks={str(SOURCE):sha(SOURCE),str(path):sha(path),str(asset):sha(asset),str(Path(__file__)):sha(__file__)}
 for name in ('dump.cs','Il2CppDumper_current/dump.cs'):
  p=ROOT.parent/'Ark_data'/name;text=p.read_text(encoding='utf8');locks[str(p)]=sha(p)
  classes={key:declaration(text,key) for key in ('HpRatioToggleChecker','ToggleablePassiveBuffAbility','PassiveAttachmentAbility','Ability.Options','Ability.FamilyGroup','Ability.FamilyGroupMask','LifeType','PhysicsRange','GridMap')}
  methods=[]
  for match in re.finditer(r'^\s*(?:public|private).*\b(?:MapToWorldPosition|WorldToMapPosition|WorldToGridPosition|WorldToMapPos|MapToWorldPos)(?:V3)?\(.*$',text,re.M):
   methods.append({'line':text[:match.start()].count('\n')+1,'signature':match.group().strip(),'previous_lines':text[max(0,match.start()-100):match.start()]})
  dumps[name]={'path':str(p),'sha256':sha(p),'declarations':classes,'coordinate_method_signatures':methods}
 bodies_path=ROOT/'packages/campaign/chapter02_behavior/skulsr.managed_bodies.reference.json';bodies=json.loads(bodies_path.read_bytes());locks[str(bodies_path)]=sha(bodies_path)
 for assembly in bodies['assemblies']:
  assert sha(assembly['path'])==assembly['sha256'];locks[assembly['path']]=assembly['sha256']
  hp=next(t for t in assembly['types'] if t['name']=='HpRatioToggleChecker');methods={m['name']:m for m in hp['methods']}
  assert methods['LoadData']['il_bytes']=='2A' and methods['OnTick']['il_bytes']=='2A'
  assert methods['_CheckCondition']['il_bytes'].startswith('1200FE15') and methods['_CheckCondition']['il_bytes'].endswith('062A')
 hot=[];matches=[]
 for folder in ('base_raw','hot_raw'):
  directory=ROOT.parent/'unpack_work/release_20260831'/folder
  for p in sorted(directory.glob('*.lua.dat')):
   raw=p.read_bytes();hot.append({'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
   if any(term in raw for term in (b'HpRatioToggleChecker',b'skulsr_t_1',b'atkup.hp_ratio')):matches.append(str(p))
 command=['rg','--files','-uu',str(ROOT.parents[1]),'-g','GameAssembly.dll','-g','global-metadata.dat','-g','libil2cpp.so','-g','!**/.git/**']
 scan=subprocess.run(command,capture_output=True,text=True);native=[x for x in scan.stdout.splitlines() if x.strip()]
 template=d['bson']['templates']['switch_mode_restart_fsm'];assert hashlib.sha256(base64.b64decode(template['document_base64'])).hexdigest()==template['document_sha256']
 simple=next(c for c in projectile['components'].values() if c['native_class']=='SimpleProjectile');assert simple['raw']['_hitNumType']==2 and simple['raw']['_maxHitNum']==1
 return {'schema':'ark-sim/skulsr-native-conflict/v1','source_locks':locks,'actual_variant':variant,'actual_checker':checker,'actual_projectile':projectile,'actual_bson_switch_mode':template,'native_declarations':dumps,'managed_stub_evidence':bodies,'hot_lua_inventory':hot,'hot_lua_exact_key_matches':matches,'native_binary_scan':{'command':command,'returncode':scan.returncode,'matches':native,'scope':'D:/Arknights workspace; absence not a claim about other drives'},'threshold_resolution':{'status':'unresolved','serialized_max':checker['raw']['_maxHpRatio'],'DB_atkup_hp_ratio':bb['atkup.hp_ratio'],'min_load_flag':0,'reason':'current/native signatures contain runtime m_maxHpRatio + Hotfix_LoadData, but no body/binary; both managed DLLs return stubs; no matching key in enumerated local Lua data','forbidden_inference':'min-load false does not establish max-load behavior; names/RVA cannot prove max override'},'hit_cap_resolution':{'native_field':'_hitNumType','value':2,'enum':'LifeType.INFINITY','inactive_field':'_maxHitNum','inactive_value':1,'runtime_contract_needed':'max_hits:null unlimited; no large numeric sentinel'},'family_resolution':{'native_mask':1,'enum':'Ability.FamilyGroupMask.ATTACK','native_options_field':'Ability.Options.familyGroup','math_profile_role_mapping':'UnitMode._attack=>ATTACK, _combat=>COMBAT; actual wrapper assignment body pending'},'coordinate_resolution':{'status':'body_unavailable','PhysicsRange_geometry':'aoemag.physics.reference.json stores both actual box collider parent chains','mapping':'not derived from method names or prefab root placement'},'actual_game_correct':False,'formal_approved':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode()
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'sha256':sha(OUT),'threshold_resolution':p['threshold_resolution']['status'],'hot_lua_files':len(p['hot_lua_inventory']),'matching_lua_files':len(p['hot_lua_exact_key_matches']),'native_binary_matches':len(p['native_binary_scan']['matches'])}))
