import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
import ark_sim
from tools.chapter06_review.build_stage_v1 import build
from tools.chapter06_review.build_life_overlay_v1 import apply
from tools.chapter06_review.stage_converter_v7 import exact
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter06_stage_join_independent_final';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pins_path=ROOT/'packages/campaign/chapter06_join/source.pins.json';pins=json.loads(pins_path.read_bytes());source_boss=ROOT/'packages/campaign/chapter06_boss/frstar2/model.json';snapshot=HERE/'draft_boss_snapshot.json';snapshot.write_bytes(source_boss.read_bytes());draftpin=sha(snapshot)
paths=[ROOT/p for p in pins]+[pins_path,ROOT/'tools/chapter06_review/build_stage_v1.py',ROOT/'tools/chapter06_review/build_life_overlay_v1.py',Path(__file__),snapshot]+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guards():return {str(p):sha(p) for p in sorted(paths)}
before=guards();assert implementation_digest()=='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b';rows=[];captures=[];inputs=[]
def reject(name,fn,data):
 inputs.append({'case':name,'input':deepcopy(data)})
 try:v=fn()
 except ValueError as e:rows.append({'case':name,'passed':True,'rejection':str(e)})
 except Exception as e:rows.append({'case':name,'passed':False,'error':repr(e)})
 else:rows.append({'case':name,'passed':False,'unexpected_acceptance':True});captures.append({'case':name,'output':v})
parent=build('level_main_06-14',snapshot,draftpin);native=json.loads((ROOT/'packages/campaign/chapter06_plans/source.plan.json').read_bytes())['stages']['level_main_06-14']['native_document'];scene=parent['scenarioDraft'];assert scene['metadata']['native_options']==native['options'] and scene['metadata']['native_predefines']==native['predefines'];assert len(scene['roster'])==len(set(scene['roster']))==12
assert scene['parameters']['deploy_capacity']==9 and scene['resources']['life']['initial']==3 and scene['resources']['dp']['initial']==10
births=sum(a['count'] for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn');assert births==50
speedid=scene['rules']['movement.speed'];speed=next(d for d in parent['definitions'] if d['id']==speedid);assert speed['parameters']['multiplier']==native['options']['moveMultiplier']==.5
assert len(parent['manifest']['metadata']['variant_bindings'])==8
rows.append({'case':'actualsource50births8variants_native9slots_DP10_life3_movehalf_fixed12','passed':True});captures.append({'case':'positive_parent','output':parent})
overlay=apply(parent,'1'*64);restore=deepcopy(overlay);restore['scenarioDraft']['resources']['life']=deepcopy(scene['resources']['life']);del restore['scenarioDraft']['metadata']['runthrough_profile'];del restore['manifest']['metadata']['goal_base_life_authoring'];assert exact(restore,parent);rows.append({'case':'only_life_profile_provenance_overlay','passed':True});captures.append({'case':'positive_overlay','output':overlay})
reject('wrong_boss_pin',lambda:build('level_main_06-14',snapshot,'0'*64),{'path':str(snapshot),'pin':'0'*64})
reject('special_s_missing_cannot_consume_ordinary',lambda:build('level_main_06-15',snapshot,draftpin),{'path':str(snapshot),'pin':draftpin})
base=json.loads(snapshot.read_bytes())
def badboss(name,change,stage='level_main_06-14'):
 p=deepcopy(base);change(p);path=HERE/(name+'.json');path.write_text(json.dumps(p,indent=2),encoding='utf8');reject(name,lambda:build(stage,path,sha(path)),p)
badboss('wrong_source_stats',lambda p:p['entities'][0]['components']['attributes']['base'].update(atk=1))
badboss('wrong_variant',lambda p:p['entities'][0]['metadata'].update(native_variant_id='enemy/not_native'))
badboss('wrong_native_reference',lambda p:p['entities'][0]['metadata']['native_reference'].update(id='enemy/foreign'))
badboss('wrong_inner_source_pin',lambda p:p['manifest']['metadata']['source_locks'].update({'packages/campaign/chapter06_sources/native.reference.json':'0'*64}))
badboss('wrong_existing_cold_source_pin',lambda p:p['manifest']['metadata']['source_locks'].update({'packages\\campaign\\chapter06_cold\\model.json':'0'*64}))
badboss('wrong_native_reference_bool',lambda p:p['entities'][0]['metadata']['native_reference'].update(useDb=1))
for name,change in [('slots_pollution',lambda p:p['scenarioDraft']['parameters'].update(deploy_capacity=12)),('fixed12_duplicate',lambda p:p['scenarioDraft'].update(roster=[p['scenarioDraft']['roster'][0]]*12)),('hidden_trap_made_visible',lambda p:p['scenarioDraft']['initialEntities'][0].update(active=True)),('parent_source_pin_pollution',lambda p:p['manifest']['metadata']['source_locks'].update({'packages/campaign/chapter06_plans/source.plan.json':'0'*64}))]:
 p=deepcopy(parent);change(p);reject(name,lambda p=p:apply(p,'1'*64),p)
after=guards();report={'core':implementation_digest(),'draft_boss_sha':draftpin,'source_boss_path':str(source_boss),'draft_snapshot_source_equal_initial':True,'cases':rows,'passed':sum(r['passed'] for r in rows),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Source/data-entry and native-only life overlay audit. OrdinaryBoss draft snapshot only for compile operands; no draftBoss behavioral/nativebody/fullstage acceptance. All altered inputs in new peer files.'}
for name,obj in [('inputs.json',inputs),('captures.json',captures),('verification.json',report)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
print(json.dumps({'cases':len(rows),'passed':report['passed'],'sha':sha(OUT/'verification.json'),'failures':[r['case'] for r in rows if not r['passed']],'guards_equal':before==after}))
