import json,hashlib,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from tools.chapter06_review.stage_converter_v6 import compose
from tools.chapter06_review.story_keys_v5 import convert,digest
OUT=ROOT/'validation/campaign/chapter06_adapter_v6_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[ROOT/'packages/campaign/chapter06_plans/source.plan.json',ROOT/'packages/campaign/chapter06_npcs/story_controls.v2.model.json',ROOT/'packages/campaign/chapter06_exit_accounting/reference_policy.json',ROOT/'tools/chapter06_review/stage_converter_v6.py',ROOT/'tools/chapter06_review/story_keys_v5.py',ROOT/'validation/campaign/chapter06_join_preparation_v1/freeze.json',Path(__file__)]+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guard():return {str(p):sha(p) for p in sorted(files)}
before=guard();native=json.loads(files[0].read_bytes())['stages']['level_main_06-15']['native_document'];nid='level_main_06-15'
defs={r['inst']['characterKey']:'unit/peer/'+r['inst']['characterKey'] for r in native['predefines']['characterInsts']}
profile={'schema':'ark-sim/story-predefined-key-profile/v1','policy':'unique_native_character_key_for_hidden_null_alias','native_id':nid,'native_document_digest':digest(native),'bindings':[{'bucket':'characterInsts','index':i,'activation_key':r['inst']['characterKey'],'definition':defs[r['inst']['characterKey']]} for i,r in enumerate(native['predefines']['characterInsts'])]}
pre=convert(native,nid,defs,story_key_profile=profile);stories={c['metadata']['native_story_key']:c for c in json.loads(files[1].read_bytes())['controls']};exitp=json.loads(files[2].read_bytes())['actionLifecycleProfile'];bindings={'enemy_1510_frstar2_s':{'unit':'unit/peer/explicit_pending_boss','motion':'WALK'}}
def data():return {'native':deepcopy(native),'pre':deepcopy(pre),'profile':deepcopy(profile),'exits':[deepcopy(exitp)]}
def run(d):return compose(d['native'],nid,bindings,{},story_controls=stories,predefined_profile=d['pre'],story_key_profile=d['profile'],action_lifecycle_profiles=d['exits'])
rows=[];inputs=[];outputs=[]
d=data();scene,controls=run(d);assert scene['parameters']['deploy_capacity']==0 and scene['resources']['dp']['initial']==0 and scene['resources']['life']['initial']==1 and len(controls)==5
assert scene['initialEntities']==pre['initial_entities'] and scene['metadata']['native_predefines']==native['predefines']
assert [a['metadata']['native_action'] for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]==[a for w in native['waves'] for f in w['fragments'] for a in f['actions']]
rows.append({'name':'actualsource_preserved_zero_slots_three_NPC_five_story','passed':True});inputs.append(d);outputs.append({'scene':scene,'controls':controls})
trials=[]
def add(name,change):
 d=data();change(d);trials.append((name,d))
add('unused_profile',lambda d:d['exits'][0].update(action=1))
add('bool_phase_index',lambda d:d['exits'][0].update(wave=False))
add('float_phase_index',lambda d:d['exits'][0].update(fragment=0.0))
add('duplicate_profile',lambda d:d['exits'].append(deepcopy(d['exits'][0])))
add('foreign_native_id',lambda d:d['exits'][0].update(native_id='level_main_06-14'))
add('int_exit_unharmful',lambda d:d['exits'][0]['lifecycle']['exit_parameters'].update(unharmful=1))
add('bool_exit_loss',lambda d:d['exits'][0]['lifecycle']['exit_parameters'].update(loss=True))
add('bad_registration',lambda d:d['pre']['initial_entities'][0].update(registration_key='foreign'))
add('active_instead_of_dormant',lambda d:d['pre']['initial_entities'][0].update(active=True))
add('source_action_bool_count_equal_one',lambda d:d['exits'][0]['native_action'].update(count=True))
add('source_action_int_managed_equal_true',lambda d:d['exits'][0]['native_action'].update(managedByScheduler=1))
add('source_action_float_route_equal_zero',lambda d:d['exits'][0]['native_action'].update(routeIndex=0.0))
add('predefine_inst_bool_favor_equal_zero',lambda d:d['pre']['initial_entities'][0]['parameters']['native_instance']['inst'].update(favorPoint=False))
add('predefine_source_bool_potential_equal_zero',lambda d:d['pre']['native_predefines']['characterInsts'][0]['inst'].update(potentialRank=False))
for name,d in trials:
 inputs.append(d)
 try:result=run(d)
 except ValueError as e:rows.append({'name':name,'passed':True,'rejection':str(e)});outputs.append(None)
 except Exception as e:rows.append({'name':name,'passed':False,'error':repr(e)});outputs.append(None)
 else:rows.append({'name':name,'passed':False,'unexpected_acceptance':True});outputs.append({'scene':result[0],'controls':result[1]})
after=guard();report={'cases':rows,'passed':sum(r['passed'] for r in rows),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Pure exact actualsource input conversion. Explicit pending Boss placeholder only for output provenance; no compiler/fullstage/native timing claim. Bool/int/float semantic equivalence may not satisfy byte/type-exact source binding.'}
for name,obj in [('inputs.json',inputs),('outputs.json',outputs),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
print(json.dumps({'cases':len(rows),'passed':report['passed'],'sha':sha(OUT/'verification.json'),'failures':[r['name'] for r in rows if not r['passed']],'guards_equal':before==after}))
