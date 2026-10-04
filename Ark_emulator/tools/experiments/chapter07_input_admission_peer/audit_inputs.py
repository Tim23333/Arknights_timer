import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_area_projection_v2_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from tools.chapter07_join.runner_providers_v1 import providers as p717
from tools.chapter07_stage_join.runner_718_providers_v1 import providers as p718
from tools.chapter06_review.stage_converter_v6 import route_ir,map_plan
OUT=ROOT/'validation/campaign/chapter07_inputs_semantic_peer_v1';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
PLAN=ROOT/'packages/campaign/chapter07_plans/source.plan.json';SOURCE=ROOT/'packages/campaign/chapter07_sources/native.reference.json';ROSTER=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
paths=[ROOT/'packages/campaign/chapter07_stage_models'/('level_main_'+s+'.native_draft.v2.json') for s in ['07-15','07-16']]
files=[Path(__file__),PLAN,SOURCE,ROSTER,ROOT/'tools/chapter06_review/stage_converter_v6.py',ROOT/'tools/chapter07_join/runner_providers_v1.py',ROOT/'tools/chapter07_stage_join/runner_718_providers_v1.py',ROOT/'tools/chapter07_strength_melee/policies_v2.py',ROOT/'tools/chapter07_predefines/policies_v1.py',ROOT/'tools/chapter07_boss/policies_v1.py',ROOT/'tools/chapter07_boss/policies_v2.py',ROOT/'tools/chapter07_ranged_consumers/policies_v1.py',ROOT/'tools/chapter07_ranged_consumers/mortar_box_v2.py',ROOT/'validation/campaign/chapter07_final3992_independent_gate/freeze.json',ROOT/'validation/campaign/chapter07_stage_mortar_source_complete/verification.json',*paths]+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
for path in paths:
 for name in load(path)['manifest']['metadata']['source_locks']:files.append(Path(name))
files=list(dict.fromkeys(files));before={str(p):sha(p) for p in files};assert implementation_digest()=='3992a0e6726dd7128b9ee36e542be38376f7488d2d8165af33bdc9c662a79000'
native=load(PLAN);source=load(SOURCE);roster=load(ROSTER);rdefs={d['id']:d for d in roster['definitions']};rows=[]
for path,reg,births,count in zip(paths,[p717(),p718()],[37,45],[6,8]):
 p=load(path);scene=p['scenarioDraft'];sid=scene['metadata']['native_id'];n=native['stages'][sid]['native_document'];meta=p['manifest']['metadata'];defs={d['id']:d for d in p['definitions']};assert len(defs)==len(p['definitions'])
 program=Compiler(providers=reg).compile(p)
 assert exact(scene['roster'],roster['manifest']['metadata']['roster']) and len(set(scene['roster']))==12
 assert exact(meta['native_options'],n['options']) and exact(meta['native_predefines'],n['predefines']) and scene['seed']==n['randomSeed']
 assert scene['parameters']['deploy_capacity']==9 and scene['resources']['dp']['initial']==10 and scene['resources']['life']=={'initial':3,'capacity':3}
 assert exact(scene['map']['tiles'],map_plan(n)['tiles']);assert exact([x['raw'] for x in scene['metadata']['rune_policy']],n['runes']) and all(x['active'] is False for x in scene['metadata']['rune_policy'])
 actions=[]
 for wi,w in enumerate(scene['timeline']['waves']):
  raww=n['waves'][wi];assert exact(w['pre_delay_seconds'],raww['preDelay']) and exact(w['post_delay_seconds'],raww['postDelay']) and exact(w['max_wait_seconds'],raww['maxTimeWaitingForNextWave'])
  for fi,f in enumerate(w['fragments']):
   assert exact(f['pre_delay_seconds'],raww['fragments'][fi]['preDelay'])
   for a in f['actions']:
    original=a['metadata']['native_action'];assert exact(original,raww['fragments'][fi]['actions'][a['metadata']['native_action_index']]);assert exact(a['count'],original['count']) and exact(a['managed'],original['managedByScheduler']) and exact(a['blocks_wave'],not original['dontBlockWave']) and exact(a['blocks_fragment'],original['blockFragment'])
    if a['kind']=='spawn':assert exact(a['spawn']['route'],route_ir(n['routes'][original['routeIndex']],len(n['mapData']['map'])));actions.append(a)
 assert sum(a['count'] for a in actions)==births and len(meta['variant_bindings'])==count
 variants=[]
 for bind in meta['variant_bindings']:
  v=source['variants'][bind['variant_id']];unit=defs[bind['unit']];c=unit['components'];original=v['native_enemy']['resolved'];stats=original['attributes'];assert exact(bind['native_reference'],v['native_reference']) and bind['native_reference'] in n['enemyDbRefs']
  for dst,src in {'max_hp':'maxHp','atk':'atk','def':'def','mres':'magicResistance','move_speed':'moveSpeed','attack_interval':'baseAttackTime'}.items():assert type(c['attributes']['base'][dst]) is not bool and c['attributes']['base'][dst]==stats[src]
  assert c['resources']['hp']['initial']==stats['maxHp'] and c['lifecycle']['leak_loss']==original['lifePointReduce'];assert c.get('abilities') and all(a in program.definitions for a in c['abilities'])
  entries=[]
  for aid in c['abilities']:
   a=defs[aid];entries.append({'ability':aid,'activation':a['activation'],'selector':a.get('selector'),'timeline':a.get('timeline'),'duration':a.get('duration_seconds'),'cooldown':a.get('cooldown_seconds')})
  variants.append({'variant':bind['variant_id'],'unit':bind['unit'],'stats':c['attributes']['base'],'native_ref':bind['native_reference'],'source_leak_loss':c['lifecycle']['leak_loss'],'runtime_components':c,'ability_consumers':entries})
 roster_rows=[]
 for eid in scene['roster']:
  assert exact(defs[eid],rdefs[eid]);cfg=defs[eid]['metadata']['config'];assert cfg['elite_phase']==2 and cfg['level']==70 and cfg['potential_rank']==0 and cfg['trust_percent']==100 and cfg['mastery']==3 and cfg['equipment_id'] is None
  selected=defs[eid]['metadata']['selected_skill_ability'];assert selected in defs[eid]['components']['abilities'] and selected in program.definitions;roster_rows.append({'entity':eid,'config':cfg,'selected_skill':selected,'base_stats':defs[eid]['components']['attributes']['base']})
 source_checks={name:sha(Path(name))==pin for name,pin in meta['source_locks'].items()};assert all(source_checks.values())
 if sid=='level_main_07-16':assert scene['cards']==['unit/ch7/predefined/mine/level1'] and scene['resources']['stock_ch7_mine']=={'initial':15,'capacity':15};assert any(d.get('metadata',{}).get('native_story_key')=='obt/tutorial/level/main_07-16' for d in defs.values())
 rows.append({'stage':sid,'display':'7-17' if sid.endswith('15') else '7-18','package_sha':sha(path),'native_births':births,'variants':variants,'fixed12':roster_rows,'source_locks_checked':source_checks,'compiled_program':program.fingerprint,'required_providers':thaw(program.metadata).get('provider_lock'), 'compiled_dependency_count':len(program.dependency_ids),'cards_separate_from_roster':scene.get('cards',[]),'native_map_routes_runes_actions_exact':True,'model_profiles':scene['metadata'],'scope':'Input/source consumer semantics and compile closure, not whole execution or client/numeric-all accuracy.'})
report={'passed':True,'core':implementation_digest(),'stages':rows,'guards_start':before,'guards_end':{str(p):sha(p) for p in files},'source_gap_confirmed':[],'resolved_profile_policy':'Native methods/client alignment are not blockers: retain declared clocks/capture/trajectory/geometry/lifecycle model profile choices. Enemy canonical stats/raw source and fixed12data exact; all selected consumers resolve through actual compiler. FOUR_STAR rune source retained but inactive normal difficulty; life-only overlay independently reviewed in companion receipt. No metadata_false automatic rejection.','mortar_reading_correction':'Initial truncated-output static suspicion omitted outerprojectile_definition; actualmodulef331/stagec940 containpdef. Fresh actualcast0/launch16/retainedsource prehitCP17/head/onephysical419 provesdeclaredspeed4/homing-reference. Exactparacurve visualcurve/client compare remainscalibration, not missingruntime capability.','scope_limits':'Current3992 independent37/36unique gate reused onlyits actual scopes; older module proofs kept originalcore. Does not certifyallunknown numericfields/client/whole or staticplanall12deployment.'}
assert report['guards_start']==report['guards_end']
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'sha':sha(OUT/'verification.json'),'stages':2,'variants':[6,8],'guards_equal':True}))
