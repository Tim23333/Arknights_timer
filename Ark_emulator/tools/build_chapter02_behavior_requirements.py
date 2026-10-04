"""Source-locked chapter02 dependency decisions, never a runtime fallback."""
import json,hashlib,argparse
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter02_sources/native.reference.json'
OUT=ROOT/'packages/campaign/chapter02_behavior/requirements.reference.json'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def walk(v,path=()):
 if isinstance(v,dict):
  yield path,v
  for k,x in v.items():yield from walk(x,path+(k,))
 elif isinstance(v,list):
  for i,x in enumerate(v):yield from walk(x,path+(i,))
def build():
 d=read(SOURCE);catalog=read(ROOT/'packages/campaign/mainline_catalog.json')
 selected=next(c['selected_native_ids'] for c in catalog['chapters'] if c['chapter']==2)
 assert selected==['main_02-09','main_02-10']
 locks={str(SOURCE.relative_to(ROOT)):sha(SOURCE),'packages/campaign/mainline_catalog.json':sha(ROOT/'packages/campaign/mainline_catalog.json'),'tools/build_chapter02_behavior_requirements.py':sha(__file__)}
 for path,row in walk(d):
  if isinstance(row.get('path'),str) and 'sha256' in row and 'bytes' in row:
   p=ROOT.parent/row['path'];assert p.is_file() and sha(p)==row['sha256'],str(p)
   locks['../'+row['path']]=row['sha256']
 entries=[]
 for vid,r in d['variants'].items():
  modes=[];issues=[]
  for mode in r['modes']:
   nodes={}
   for role,node in mode['nodes'].items():
    raw=node.get('raw',{});wait=raw.get('_waitForAttackEvent');binding=node.get('animation_binding') or {}
    events=[e for e in binding.get('events',[]) if e['name']=='OnAttack']
    nodes[role]={'path_id':node.get('path_id'),'native_class':node.get('native_class'),'raw':raw,'animation_binding':binding,
     'clock_consumer':{'strategy':'source_event' if wait==1 else 'specified_predelay' if wait==0 else 'no_attack',
      'events':events if wait==1 else [],'predelay':raw.get('_preDelay') if wait==0 else None}}
   modes.append({'mode_index':mode['index'],'mode_path_id':mode['mode_path_id'],'raw_mode':mode['raw_mode'],'nodes':nodes})
  special=[{'path_id':pid,'native_class':c['native_class'],'raw':c['raw']} for pid,c in r['components'].items() if c['native_class'] in ('AuraAbility','RangeModifier','TargetValidator','PhysicsRange','CircleRange','HpRatioToggleChecker','ToggleablePassiveBuffAbility','PassiveAttachmentAbility','AdvancedSelector')]
  if r['source_disagreements']:issues+=['serialized_checker_.4_vs_DB_.5_unresolved_LoadData_and_version']
  if any(x['native_class']=='PhysicsRange' for x in special):issues+=['physics_overlap_box_range_consumer_not_implemented']
  if any(x['native_class']=='AuraAbility' for x in special):issues+=['source_range_modifier_load_and_target_validator_adapter_require_content']
  if any(m['nodes']['_attack'].get('raw',{}).get('_projectileKey') for m in modes):issues+=['projectile_profile_content_required_M26_primitives_available']
  entries.append({'variant_id':vid,'native_id':r['native_enemy']['native_id'],'stages':r['stages'],'native_DB':r['native_enemy'],
   'prefab_source':d['prefabs'][r['prefab_key']]['source'],'modes':modes,'special_components':special,
   'geometry_sources':d['prefabs'][r['prefab_key']]['geometry_sources'],'source_disagreements':r['source_disagreements'],
   'existing_plain_model':r['normal_model_authored'],'reusable_primitives':['damage.pipeline physical/arts','Buff attributes/aura/on_remove','behavior.decision pure eligibility','M17 projectile instance','resource.changed passive mode/buff restart'],
   'model_gaps':issues,'client_pending':['native permission/comparator/LoadData/method bodies unavailable','source version correspondence','native callback/animation scale/physics alignment'],
   'actual_game_correct':False})
 stage_records={}
 for k,s in d['stages'].items():
  n=s['native_level_document'];counts=Counter(a['key'] for w in n['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='SPAWN' for _ in range(a['count']))
  assert sum(counts.values())==s['spawn_count']
  stage_records[k]={'source':s['source'],'wave_spawn_count':sum(counts.values()),'wave_counts':dict(counts),'raw_waves':n['waves'],'raw_used_routes':{str(i):n['routes'][i] for i in s['used_route_indices']},'raw_options':n['options'],'raw_controls':s['controls'],'active_runes':s['active_runes'],'inactive_runes':s['inactive_runes'],'route_consumers':['WALK/FLY actual native motion','MOVE/WAIT_FOR_SECONDS','WAIT_CURRENT_FRAGMENT_TIME relative to fragment actual start'],'not_executable':True}
 c1path=ROOT/'packages/campaign/chapter01_sources/native.reference.json';c1=read(c1path);locks[str(c1path.relative_to(ROOT))]=sha(c1path)
 ledger={}
 for level,s in c1['stages'].items():
  n=s['native_level_document'];wave=sum(a['count'] for w in n['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='SPAWN')
  assert wave==s['spawn_count'];pre=n.get('predefines',{})
  ledger[level]={'wave_enemy_births':wave,'source_declared_spawn_count':s['spawn_count'],'predefined_instances':pre.get('tokenInsts',[]),'raw_predefines_keys':list(pre),'wave_count_excludes_player_owned_summons_and_predefined_actors':True}
 calls=[]
 for owner,row in c1['enemies'].items():
  for pid,c in row['prefab']['components'].items():
   for path,v in walk(c['raw']):
    for key,value in v.items():
     if any(term in key.lower() for term in ('spawn','summon','createenemy','tokenkey')) and value not in (None,False,0,'',[],{}):calls.append({'owner':owner,'component':pid,'native_class':c['native_class'],'path':list(path)+[key],'value':value})
 # This is an explicit serialized-field/BSON scope, not a missing-body proof.
 return {'schema':'ark-sim/chapter02-behavior-requirements/v1','status':'source_dependency_plan_unapproved','source_locks':locks,'stages':stage_records,'variants':entries,'chapter01_ledger':ledger,'chapter01_nonwave_enemy_creation_serialized_candidates':calls,'chapter01_bson_templates':{k:v['parsed'] for k,v in c1['bson']['templates'].items()},'chapter01_nonwave_scope':'30/45 count SPAWN actions only; serialized enemy closure/templates show candidates above. Native method bodies unavailable; do not count all World births as enemies or assume owned/predefined births included. Runtime ledger must classify side/definition/registration/ownership/cause.','formal_approved':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();p=build();b=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==b
 else:OUT.write_bytes(b)
 print(json.dumps({'passed':True,'check':a.check,'variants':len(p['variants']),'source_locks':len(p['source_locks']),'output_sha256':sha(OUT),'chapter01_ledger':{k:v['wave_enemy_births'] for k,v in p['chapter01_ledger'].items()},'serialized_nonwave_candidates':len(p['chapter01_nonwave_enemy_creation_serialized_candidates'])}))
