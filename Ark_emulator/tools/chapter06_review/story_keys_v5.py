"""Opt-in, source-bound null-alias registration; no stage/kernel mutation."""
from copy import deepcopy
import hashlib,json
SCHEMA='ark-sim/story-predefined-key-profile/v1'
POLICY='unique_native_character_key_for_hidden_null_alias'
def digest(native):
 return hashlib.sha256(json.dumps(native,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def _records(native):
 result=[];aliases=set()
 for bucket in ['characterInsts','tokenInsts']:
  records=native['predefines'].get(bucket) or []
  if not isinstance(records,list):raise ValueError('Nonempty native instance bucket requires array')
  for index,record in enumerate(records):
   if type(record.get('hidden')) is not bool:raise ValueError('Native hidden must be strict bool')
   alias=record.get('alias')
   if alias is not None:
    if type(alias) is not str or not alias or alias in aliases:raise ValueError('Native aliases must be globally unique nonempty strings')
    aliases.add(alias)
   key=record['inst']['characterKey']
   if type(key) is not str or not key:raise ValueError('Native characterKey must be nonempty string')
   result.append((bucket,index,record))
 return result
def validate(native,native_id,profile):
 records=_records(native);need={(b,i) for b,i,r in records if r['hidden'] and r['alias'] is None}
 if profile is None:
  if need:raise ValueError('Hidden null alias requires explicit source story-key profile')
  return {}
 if not isinstance(profile,dict) or set(profile)!={'schema','policy','native_id','native_document_digest','bindings'}:raise ValueError('Exact explicit story-key profile fields required')
 if profile['schema']!=SCHEMA or profile['policy']!=POLICY or profile['native_id']!=native_id or profile['native_document_digest']!=digest(native):raise ValueError('Story-key profile source identity mismatch')
 if not isinstance(profile['bindings'],list):raise ValueError('Story-key bindings must be array')
 requests=[]
 for wave in native['waves']:
  for fragment in wave['fragments']:
   for action in fragment['actions']:
    if action['actionType']=='ACTIVATE_PREDEFINED':
     key=action['key']
     if type(key) is not str or not key or type(action['count']) is not int or action['count']!=1:raise ValueError('Story activation key and count must be source strict')
     requests.append(key)
 if len(requests)!=len(set(requests)):raise ValueError('Duplicate story activation keys are not silently resolved')
 by_position={(b,i):r for b,i,r in records};out={};keys=set();reserved={r['alias'] for _,_,r in records if r['alias'] is not None}
 for entry in profile['bindings']:
  if not isinstance(entry,dict) or set(entry)!={'bucket','index','activation_key','definition'}:raise ValueError('Story-key binding fields must be exact')
  bucket,index,key,definition=(entry[k] for k in ['bucket','index','activation_key','definition'])
  if type(bucket) is not str or bucket not in ['characterInsts','tokenInsts'] or type(index) is not int or index<0:raise ValueError('Story-key bucket/index require strict source types')
  identity=(bucket,index)
  if identity not in need or identity in out:raise ValueError('Story-key binding must identify one hidden null-alias instance')
  if type(key) is not str or not key or key in keys or key in reserved or key not in requests:raise ValueError('Story-key must be actual unique nonconflicting ACTIVATE_PREDEFINED key')
  if type(definition) is not str or not definition:raise ValueError('Story-key definition must be explicit nonempty ID')
  record=by_position[identity]
  matches=[r for _,_,r in records if (r['alias'] if r['alias'] is not None else r['inst']['characterKey'])==key]
  if len(matches)!=1 or record['inst']['characterKey']!=key:raise ValueError('Story-key must match exactly one real source characterKey')
  keys.add(key);out[identity]=deepcopy(entry)
 if set(out)!=need:raise ValueError('Every hidden null-alias source instance requires its own binding')
 return out
def convert(native,native_id,definitions,*,story_key_profile=None):
 """Pure predefine profile; does not convert special spawns or story actions."""
 bindings=validate(native,native_id,story_key_profile);records=_records(native)
 if any(native['predefines'].get(b) for b in ['characterCards','tokenCards']):raise ValueError('Cards require separate exact stock source profile')
 if not isinstance(definitions,dict):raise ValueError('Explicit native character definition map required')
 rows=len(native['mapData']['map']);initial=[]
 for bucket,index,record in records:
  character=record['inst']['characterKey'];definition=definitions.get(character)
  if type(definition) is not str or not definition:raise ValueError('Missing exact native actor definition')
  identity=(bucket,index);mapping=bindings.get(identity)
  if mapping is not None and mapping['definition']!=definition:raise ValueError('Source profile definition disagrees with actor binding')
  item={'definition':definition,'position':{'row':rows-1-record['position']['row'],'col':record['position']['col']},'facing':record['direction'].lower(),'parameters':{'native_bucket':bucket,'native_instance':deepcopy(record)}}
  if record['hidden']:
   item.update(active=False,registration_key=mapping['activation_key'] if mapping else record['alias'])
   if mapping:item['parameters']['native_story_key_binding']=deepcopy(mapping)
   else:item['instanceAlias']=record['alias']
  elif record['alias'] is not None:item['instanceAlias']=record['alias']
  initial.append(item)
 return {'native_predefines':deepcopy(native['predefines']),'initial_entities':initial,'card_bindings':[],'resources':{}}
