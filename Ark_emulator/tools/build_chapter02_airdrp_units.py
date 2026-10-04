"""Exact stage-variant ground units; birth/body gaps are admission failures."""
from pathlib import Path
from copy import deepcopy
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json';ATTACKS=ROOT/'packages/campaign/chapter02_sources/attacks.model.json';OUT=ROOT/'packages/campaign/chapter02_units/airdrp.post_born.partial.json'
PINS={SOURCE:'97447895b3edc69f0f60113ea96bc240c25c0fe980897614e93a94dd75e0d492',ATTACKS:'92ee425de448f7b87610e9cc626d480280af2dd5296939ec9a013c20e9a5e0d0'}
RUNTIME=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate';CORE='c77ce7a46101cf903fd9c6c56dcabddf5775008d091365cd7486ddeb47b8d740'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(require_complete=False,source=None,attacks=None):
 import UnityPy
 for path,pin in PINS.items():
  if sha(path)!=pin:raise ValueError('frozen source bytes drift: '+str(path))
 d=json.loads(SOURCE.read_bytes()) if source is None else deepcopy(source);library=json.loads(ATTACKS.read_bytes()) if attacks is None else deepcopy(attacks)
 import sys
 sys.path.insert(0,str(ROOT))
 from tools.build_mainline_dependencies import resolve_enemy
 db_source=d['source_identities']['enemy_DB'];db_path=ROOT.parent/db_source['path'];assert sha(db_path)==db_source['sha256'];db=json.loads(db_path.read_bytes())
 stage=d['stages']['level_main_02-09'];requested={'enemy_1013_airdrp','enemy_1013_airdrp_2'};selected=[]
 for vid in stage['resolved_variant_ids']:
  if vid not in d['variants']:raise ValueError('stage variant not resolved')
  row=d['variants'][vid]
  if row['native_enemy']['native_id'] in requested:selected.append((vid,row))
 if len(selected)!=2 or {row['native_enemy']['native_id'] for _,row in selected}!=requested:raise ValueError('stage must resolve exactly both air troop variants')
 units=[];abilities=[];selectors=[];behaviors=[];records=[];locks={str(p.relative_to(ROOT)):pin for p,pin in PINS.items()};locks['../'+db_source['path']]=sha(db_path);cache={}
 for vid,row in selected:
  enemy=row['native_enemy'];resolved=enemy['resolved'];attrs=resolved['attributes'];native_id=enemy['native_id']
  if resolve_enemy(db,row['native_reference'])!=enemy:raise ValueError('variant DB/level/overwritten resolution differs from current pinned raw data')
  token=hashlib.sha256(json.dumps({'reference':row['native_reference'],'resolved':resolved},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:16]
  if vid!=f"{native_id}@{enemy['native_level']}/{token}":raise ValueError('variant identity does not bind exact native reference and resolved data')
  if row['variant_id']!=vid or enemy['native_level']!=0 or enemy['stage_override'] is not None:raise ValueError('selected level/override needs a new audited variant binding')
  if resolved['motion']!='WALK' or resolved['applyWay']!='MELEE':raise ValueError('ground melee source drift, never classify by airdrop name')
  if any(resolved.get(k) for k in ('skills','talentBlackboard','spData')):raise ValueError('unconsumed skill/talent/SP data requires a new driver')
  for rawrow in enemy['raw_rows']:
   native=rawrow['enemyData']
   if any(native.get(k) for k in ('skills','talentBlackboard','spData')):raise ValueError('raw source skill/talent/SP dependency unconsumed')
  if len(row['modes'])!=1 or not row['normal_model_authored']:raise ValueError('plain source combat closure not authored')
  prefab=d['prefabs'][row['prefab_key']];path=ROOT.parent/prefab['source']['path'];assert sha(path)==prefab['source']['sha256'];locks['../'+prefab['source']['path']]=sha(path)
  if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
  for pid,c in prefab['components'].items():
   if cache[path][int(pid)].read_typetree()!=c['raw']:raise ValueError('actual prefab component mismatch')
  roots=[(pid,c) for pid,c in row['components'].items() if c['native_class']=='Enemy' and c['gameobject_path_id']==prefab['root_gameobject_path_id']];movers=[(pid,c) for pid,c in row['components'].items() if c['native_class']=='MoveController'];assert len(roots)==len(movers)==1
  root_pid,root=roots[0];move_pid,mover=movers[0];raw=root['raw'];move=mover['raw'];mode=row['modes'][0];combat=mode['nodes']['_combat'];cr=combat['raw']
  assert combat['native_class']=='MeleeAttack' and mode['nodes']['_attack']['status']==mode['nodes']['_attackTrigger']['status']=='native_null'
  assert raw['_modes']==[{'m_FileID':0,'m_PathID':mode['mode_path_id']}]
  if raw['_commonAbilities'] or mode['raw_mode']['_generalAbilities'] or cr['_activeBuffs']:raise ValueError('unconsumed common/mode/buff dependencies')
  special=raw['_specialBlockCondition'];assert special['_type']==0 and not special['_buffKeyPairs'] and not special['_filterTags']
  assert (cr['_waitForAttackEvent'],cr['_selectTargetSource'],cr['_atkScale'],cr['_damageType'],cr['_elementDamageType'])==(1,2,1.0,1,0)
  events=[e for e in combat['animation_binding']['events'] if e['name']=='OnAttack'];assert len(events)==1 and events[0]['frame']==13
  for key in ('maxHp','atk','def','magicResistance','moveSpeed','attackSpeed','baseAttackTime','massLevel'):
   if key not in attrs:raise ValueError('required attribute source absent: '+key)
  abilities_for_variant=[a for a in library['abilities'] if a.get('metadata',{}).get('variant_id')==vid]
  if len(abilities_for_variant)!=1:raise ValueError('exact source attack variant missing/ambiguous')
  ability=deepcopy(abilities_for_variant[0]);sid=ability['selector'];matching=[s for s in library['selectors'] if s['id']==sid];assert len(matching)==1;selector=deepcopy(matching[0])
  assert selector['region']=={'type':'all','blocked_only':True};assert ability['timeline']==[{'at_seconds':13/30,'effect':{'op':'damage','damage_type':'physical','scale':1.0}}]
  uid='unit/chapter02/'+vid.replace('@','/level_');bid='behavior/chapter02/'+vid.replace('@','/level_')
  base={'max_hp':attrs['maxHp'],'atk':attrs['atk'],'def':attrs['def'],'mres':attrs['magicResistance'],'move_speed':attrs['moveSpeed'],'attack_interval':attrs['baseAttackTime'],'attack_speed_ratio':attrs['attackSpeed']/100,'mass_level':attrs['massLevel'],'block_cost':raw['_blockVolume'],'block_count':0}
  if type(base['block_cost']) is not int or base['block_cost']<=0:raise ValueError('native block volume invalid')
  unit={'id':uid,'kind':'entity','tags':['enemy','ground'],'metadata':{'native_id':native_id,'native_variant_id':vid,'native_level':0,'native_stage_override':None,'native_motion':'WALK','native_category':1,'birth_delay_seconds_source':raw['_delayToBorn'],'post_born_model_only':True},'components':{'attributes':{'base':base},'resources':{'hp':{'initial':attrs['maxHp'],'capacity':attrs['maxHp'],'role':'health'}},'spatial':{'steering':{'rule':'rule/chapter02/unit_steering','parameters':{'response_factor':move['_steeringFactor'],'max_acceleration':move['_maxSteeringForce'],'arrival_radius':.05}}},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':resolved['lifePointReduce']},'abilities':[ability['id']],'behavior':{'machine':bid}}}
  behaviors.append({'id':bid,'kind':'behavior','initial':'active','states':{'active':{}},'transitions':[],'decision':{'rule':'rule/ark_behavior_decision','default_mode':0,'profiles':[{'mode':0,'selectors':[{'key':'combat','selector':sid}],'cast_groups':[{'key':'combat','abilities':[ability['id']]}],'parameters':{'target_key':'combat','blocked_target':True,'stop_on_target':True,'stop_cast_groups':['combat']}}]}})
  units.append(unit);abilities.append(ability);selectors.append(selector);records.append({'variant_id':vid,'native_reference':enemy,'unit':uid,'ability':ability['id'],'selector':sid,'behavior':bid,'root_path_id':root_pid,'native_root':raw,'mode':mode,'mover_path_id':move_pid,'native_mover':move,'prefab_source':prefab['source'],'DB_defined_mass_zero_preserved':base['mass_level']==0,'model_policy':{'enemy_block_capacity_zero':'declared default; DBblockCnt m_defined false not consumed as realzero','steering':'bounded proportional velocity uses serialized8/10; arrival_radius .05 is declared model','body_width':move['_halfBodyWidth'],'body_width_collision_not_implemented':True}})
 if require_complete:raise ValueError('complete/native closure unresolved: born1.5s callbacks, FSM/target/clock/body semantics')
 return {'schemaVersion':2,'manifest':{'id':'chapter02/ground_air_troop_units','requires':['preset/ark_standard'],'metadata':{'status':'post_born_source_stats_and_declared_combat_model','builder_sha256':sha(__file__),'required_runtime':CORE,'source_locks':locks,'stage_native_id':'level_main_02-09','exact_stage_variant_bindings':records,'model_gaps':['source delayToBorn1.5 and birth interaction window not consumed by this active post-born prototype','native body width/separation physics not implemented'],'client_pending':['native Enemy Born/EndBorneDelay callback and targetability timing','INPUT_TARGET2 wrapper/permission/FSM and comparator methods','animation scaling and cooldown/source-version alignment','steering formula and arrival .05 native unverified'],'actual_game_correct':False,'formal_approved':False}},'entities':units,'abilities':abilities,'selectors':selectors,'behaviors':behaviors,'rules':[{'id':'rule/chapter02/unit_steering','kind':'rule','contract':'movement.steering','implementation':{'type':'provider','provider':'ark.movement.steering_velocity'}}]}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'units':len(p['entities']),'sha256':sha(OUT),'native_correct':False}))
