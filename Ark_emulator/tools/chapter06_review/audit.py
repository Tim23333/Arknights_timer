import json,hashlib,base64,re
from pathlib import Path
from collections import Counter
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';OUT=ROOT/'validation/campaign/chapter06_review'
OUT.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,v):
 with p.open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
FILES=list((ROOT/'tools/chapter06').rglob('*.py'))+[Path(__file__)]+list((ROOT/'packages/campaign').glob('chapter06_*/*.json'))+[ROOT/'packages/campaign/mainline_catalog.json',ROOT/'tools/build_reference_stage_scenario_v2.py']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
def guard():return {str(p):sha(p) for p in sorted(set(FILES))}
before=guard();plan=read(ROOT/'packages/campaign/chapter06_plans/source.plan.json');pre=read(ROOT/'packages/campaign/chapter06_predefines/source.reference.json');catalog=read(ROOT/'packages/campaign/mainline_catalog.json')
selected=[r for r in catalog['stages'] if r['selected'] and r['chapter']==6]
assert {r['native_id'] for r in selected}=={'main_06-14','main_06-15'}
def registration_map(native,requests):
 instances=[]
 for bucket in ['characterInsts','tokenInsts']:
  for index,item in enumerate(native['predefines'].get(bucket) or []):instances.append((bucket,index,item))
 result=[]
 for request in requests:
  matches=[(b,i,x) for b,i,x in instances if (x['alias'] if x['alias'] is not None else x['inst']['characterKey'])==request]
  if len(matches)!=1:raise ValueError('Source key requires exactly one predefined instance: '+request)
  bucket,index,item=matches[0]
  result.append({'source_key':request,'native_alias':item['alias'],'native_character_key':item['inst']['characterKey'],'native_bucket':bucket,'native_index':index,'raw_native':deepcopy(item),'proposed_registration_key':request,'source_identity':{'level':native['levelId'],'bucket':bucket,'index':index},'mapping_basis':'Exact alias if supplied; otherwise exact native ACTIVATE_PREDEFINED characterKey and cardinality==1; no avatar/UI-name fallback','runtime_instance_alias':None if item['alias'] is None else item['alias'],'runtime_initial_active':False})
 return result
RESULT=[]
for name,s in plan['stages'].items():
 native=s['native_document'];FILE=ROOT/'packages/campaign/native_reference'/(name+'.json');assert read(FILE)==native;FILES.append(FILE)
 actions=[{'wave':wi,'fragment':fi,'action':ai,'native':a} for wi,w in enumerate(native['waves']) for fi,f in enumerate(w['fragments']) for ai,a in enumerate(f['actions'])]
 spawn=[a for a in actions if a['native']['actionType']=='SPAWN'];counts=Counter()
 for a in spawn:counts[a['native']['key']]+=a['native']['count']
 assert sum(counts.values())==s['spawn_count'] and dict(counts)==s['spawn_by_key']
 controls=[a for a in actions if a['native']['actionType']!='SPAWN']
 keys=[a['native']['key'] for a in controls if a['native']['actionType']=='ACTIVATE_PREDEFINED']
 if name=='level_main_06-14':
  branch=native['branches']['frstar_frosts'];phaseactions=[a for phase in branch['phases'] for a in phase['actions']]
  keys += [a['key'] for a in phaseactions if a['actionType']=='ACTIVATE_PREDEFINED']
 mapping=registration_map(native,keys)
 used=sorted({a['native']['routeIndex'] for a in spawn});assert used==s['used_routes']
 RESULT.append({'internal':name,'display':'6-16' if name.endswith('14') else '6-17','native_sha':sha(FILE),'options':native['options'],'waves':native['waves'],'routes':native['routes'],'used_routes':used,'active_route_checkpoint_counts':s['used_checkpoint_counts'],'births':sum(counts.values()),'spawn_counts':dict(counts),'variants':[{'id':v,'reference':plan['variants'][v]['native_reference'],'attributes':plan['variants'][v]['native_enemy']['resolved']['attributes']} for v in s['variant_ids']],'controls':controls,'predefines':native['predefines'],'hard_predefines':native.get('hardPredefines'),'branches':native.get('branches'),'registration_mapping':mapping,'runes':native['runes'],'map':{'rows':s['map_plan']['rows'],'cols':s['map_plan']['cols']},'tile_counts':s['tile_cell_counts'],'special_spawn_flags':[a for a in spawn if a['native'].get('isUnharmfulAndAlwaysCountAsKilled')]})
STORIES=[]
for key,value in pre['stories'].items():
 raw=base64.b64decode(value['payload_base64'],validate=True);assert hashlib.sha256(raw).hexdigest()==value['payload_sha256']
 source=ROOT.parent/value['source']['path'];assert sha(source)==value['source']['sha256'];FILES.append(source)
 actual=source.read_bytes();assert actual[value['payload_offset']:value['payload_offset']+len(raw)]==raw
 script=raw.decode('utf8',errors='strict');commands=[]
 for line,text in enumerate(script.splitlines(),1):
  if not text.strip():continue
  match=re.fullmatch(r'\[([A-Za-z_]+)(?:\((.*?)\))?\]\s*(.*)',text);assert match,(key,line,text)
  commands.append({'line':line,'command':match[1],'parameters':match[2],'text':match[3],'raw_line':text})
 assert [x['command'] for x in commands]==[x['command'] for x in value['commands'] if x['command']]
 assert commands[0]['command']=='HEADER' and commands[0]['parameters']=='is_skippable=false, is_autoable=false'
 assert all(x['command'] in ['HEADER','PopupDialog','Blocker'] for x in commands)
 assert commands[-1]['command']=='Blocker' and commands[-1]['parameters']=='fadetime=0.3, block=true, a=0'
 txt=OUT/(key.rsplit('/',1)[1]+'.utf8.txt')
 with txt.open('x',encoding='utf8') as f:f.write(script)
 STORIES.append({'key':key,'source':value['source'],'payload_sha':value['payload_sha256'],'strict_UTF8_commands':commands,'frozen_export_text_differs':script!=value['script'],'decode_policy':'Decode preserved payload bytes as strict UTF8; frozen existing export remains untouched','runtime_consumed':False})
tests=[];native=plan['stages']['level_main_06-15']['native_document'];keys=['char_002_amiya','char_017_huang','char_367_swllow'];assert len(registration_map(native,keys))==3;tests.append({'name':'source_null_alias_character_keys_unique','passed':True})
for label,modified,request in [('duplicate',deepcopy(native),'char_002_amiya'),('invented_avatar',native,'$avatar_amiya'),('unknown',native,'amiya')]:
 if label=='duplicate':modified['predefines']['characterInsts'].append(deepcopy(modified['predefines']['characterInsts'][0]))
 try:registration_map(modified,[request]);raise AssertionError('Ambiguous/unknown source accepted')
 except ValueError:tests.append({'name':label+'_reject','passed':True})
assert sum(sum(c['command']=='PopupDialog' for c in s['strict_UTF8_commands']) for s in STORIES)==7
after=guard();unchanged=all(after[k]==v for k,v in before.items());assert unchanged
write(OUT/'audit.json',{'selected_catalog_rows':selected,'source_plan_sha':sha(ROOT/'packages/campaign/chapter06_plans/source.plan.json'),'predefined_source_sha':sha(ROOT/'packages/campaign/chapter06_predefines/source.reference.json'),'stage_facts':RESULT,'stories':STORIES,'mapping_tests':tests,'guards_start':before,'guards_end':after,'start_guard_equal':unchanged,'scope':'Independent source/data/API audit, no runtime source changes and no stage execution. 7 dialogues/5 stories/3 native character activation keys preserved.','whole_stage_started':False,'runtime_authored':False})
print(json.dumps({'report':str(OUT/'audit.json'),'sha':sha(OUT/'audit.json'),'stages':[(x['internal'],x['births'],x['options']['characterLimit']) for x in RESULT],'story_count':len(STORIES),'mapping_tests':tests},ensure_ascii=False))
