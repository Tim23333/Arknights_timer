import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def walk(v):
 if isinstance(v,dict):
  yield v
  for x in v.values():yield from walk(x)
 elif isinstance(v,list):
  for x in v:yield from walk(x)
def audit():
 native=read(ROOT/'packages/campaign/chapter06_sources/native.reference.json');results=[];pins={};families=['melee_v2','snmage_v2','snslime','frozen_melee']
 for family in families:
  path=ROOT/'packages/campaign/chapter06_units'/family/'model.json';p=read(path);pins[str(path)]=sha(path)
  for source,pin in p['manifest']['metadata']['source_locks'].items():assert sha(ROOT/source)==pin;pins[str(ROOT/source)]=pin
  bindings=p['manifest']['metadata'].get('variant_bindings') or [{'variant_id':p['manifest']['metadata']['native_variant_id'],'unit_definition':p['entities'][0]['id']}]
  entities={e['id']:e for e in p['entities']}
  for binding in bindings:
   raw=native['variants'][binding['variant_id']];a=raw['native_enemy']['resolved']['attributes'];actor=entities[binding['unit_definition']];base=actor['components']['attributes']['base']
   for field,key in [('max_hp','maxHp'),('atk','atk'),('def','def'),('mres','magicResistance'),('move_speed','moveSpeed'),('attack_interval','baseAttackTime')]:assert base[field]==a[key]
   assert actor['components']['resources']['hp']['initial']==a['maxHp'] and base['attack_speed_ratio']==a['attackSpeed']/100
   prefab=raw['prefab_key'];animation=native['animations'][prefab]['parsed'];frames=[e['frame'] for name,x in animation['animations'].items() if name.startswith('Attack') for e in x['events'] if e['name']=='OnAttack'];abilities=[x for x in p['abilities'] if x['id'] in actor['components']['abilities']]
   for ability in abilities:
    seconds=ability['timeline'][0]['at_seconds'];assert seconds*30 in frames
   passives=[]
   for buff in walk(raw['passive_and_skill_components']):
    if buff.get('templateKey')=='e2c_frozen_atkscale':
     bb=buff['blackboard'] or raw['native_enemy']['resolved'].get('talentBlackboard',[])
     scale=next(x['value'] for x in bb if x['key'].split('.')[-1]=='atk_scale');assert buff['isSilenceable']==0;passives.append({'scale':scale,'source_blackboard':bb,'isSilenceable':0,'raw_buff':buff})
   results.append({'family':family,'variant':binding['variant_id'],'unit':actor['id'],'native_reference':raw['native_reference'],'source_attributes':a,'source_attack_frames':frames,'timeline_frames':[x['timeline'][0]['at_seconds']*30 for x in abilities],'target_frozen_passives':passives,'passed':True})
 template=native['bson_templates']['templates']['e2c_frozen_atkscale']['parsed'];actions=template['eventToActions']['ON_CALCULATE_DAMAGE'];assert actions[0]['_targetType']=='TARGET' and actions[0]['_abnormalFlag']=='FROZEN' and actions[1]['_atkScaleKey']=='atk_scale' and actions[1]['_overwriteAtkScale'] is False
 death=native['bson_templates']['templates']['projectile_on_killed']['parsed']['eventToActions']['ON_OWNER_KILLED'];assert death[0]['_targetType']=='SOURCE' and death[0]['_abnormalFlag']=='SILENCED' and death[0]['_isUnset'] is True
 return {'variants':results,'source_pins':pins,'source_bson_frozen_hook':actions,'source_bson_death_hook':death,'policies_pending':['Undefined tableimmunity getter defaultFalse is declaredreference,notencodedFalse','Windup minimumspeed.01/reference normalizedAS formula;native maxanimscale relation tohit-frame clamp unresolved','Planar homing/radius/coordinate policies replaceable,notnativebody/clientcalibration','Fixed publictable/source version andrealcurrentmodule values;noActorname inferredmechanisms'],'runtime_complete_stage':False}
