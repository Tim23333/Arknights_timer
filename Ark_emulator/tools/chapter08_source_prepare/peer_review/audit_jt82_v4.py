import sys,json,hashlib
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_buff_lifetime_v4_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_stage_join.runner_providers_v2 import providers
from tools.chapter08_stage_join.inactive_branches_v1 import compose
OUT=ROOT/'validation/campaign/chapter08_jt82_input_peer_v4';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_bytes())
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
P=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v5.json';L=P.with_name('level_main_08-16.native_draft.v5.life99999.v1.json');C=ROOT/'scenarios/campaign/chapter08/level_main_08-16/public_plan_v1/commands.json';S=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json'
p=load(P);life=load(L);cmd=load(C);source=load(S);stage=source['stages']['level_main_08-16'];native=stage['native_document'];scene=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']}
files=[P,L,C,S,Path(__file__),ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/chapter08_stage_join/runner_providers_v1.py',ROOT/'tools/chapter08_stage_join/inactive_branches_v1.py']+[Path(x) for x in p['manifest']['metadata']['source_locks']]+list((ROOT/'tools/chapter08_boss').glob('*policy*.py'))+list((ROOT/'tools/chapter08_special').glob('*policies*.py'))+list((ROOT/'tools/chapter08_ranged').glob('*policies*.py'))+[ROOT/'tools/chapter08_environment/policies_v1.py']+[x for x in (RUNTIME/'ark_sim').rglob('*') if x.suffix in ('.py','.json')]
def guards():return {str(x):sha(x) for x in sorted(set(files)) if x.is_file()}
files += [ROOT/'tools/chapter08_stage_join/runner_providers_v2.py',ROOT/'tools/chapter08_buff_lifetime/policies_v1.py',ROOT/'tools/chapter08_buff_lifetime/talula_providers_v1.py',ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v8.dynamic.json',ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.json']
before=guards();assert implementation_digest()=='7e76e49e8b196f1c7ec6d3a08c7760cbb4ebc7eaa02ef778f6e71c820549fef8'
for name,pin in p['manifest']['metadata']['source_locks'].items():assert sha(Path(name))==pin
assert exact(scene['metadata']['native_options'],native['options']) and exact(p['manifest']['metadata']['native_predefines'],native['predefines'])
assert scene['parameters']['deploy_capacity']==9 and scene['resources']['dp']['initial']==10 and scene['resources']['life']['initial']==3
mp=native['mapData'];assert len(scene['map']['tiles'])==len(mp['map'])*len(mp['map'][0])
for row,ids in enumerate(mp['map']):
 for col,index in enumerate(ids):
  raw=mp['tiles'][index];wanted={k:deepcopy(raw.get(k)) for k in ('tileKey','heightType','blackboard','effects')};wanted['buildableType']={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3}[raw['buildableType']];wanted['passableMask']={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3}[raw['passableMask']];assert exact(scene['map']['tiles'][row*scene['map']['cols']+col],wanted)
assert exact(scene['metadata']['inactive_source_branches']['native_branches'],native['branches'])
assert exact(scene['metadata']['empty_hard_predefines']['native'],native['hardPredefines'])
actions=[];births=0
for wi,(nw,w) in enumerate(zip(native['waves'],scene['timeline']['waves'])):
 assert len(nw['fragments'])==len(w['fragments'])
 for fi,(nf,f) in enumerate(zip(nw['fragments'],w['fragments'])):
  assert len(nf['actions'])==len(f['actions'])
  for ai,(na,a) in enumerate(zip(nf['actions'],f['actions'])):
   assert exact(na,a['metadata']['native_action'])
   assert a['count']==na['count'] and a['delay_seconds']==na['preDelay'] and a['interval_seconds']==na['interval']
   if na['actionType']=='SPAWN':
    births+=na['count'];route=deepcopy(native['routes'][na['routeIndex']]);actual=a['spawn']['route'];top=lambda pos:{'row':scene['map']['rows']-1-pos['row'],'col':pos['col']};route['startPosition']=top(route['startPosition']);route['endPosition']=top(route['endPosition']);route['checkpoints']=route.get('checkpoints') or []
    for cp in route['checkpoints']:
     if cp.get('position') is not None:cp['position']=top(cp['position'])
    for key,value in route.items():assert exact(actual[key],value),(wi,fi,ai,key)
   actions.append({'wave':wi,'fragment':fi,'action':ai,'type':na['actionType'],'key':na['key'],'runtime_kind':a['kind']})
assert births==32 and len(stage['variant_ids'])==5
variants=[]
for binding in p['manifest']['metadata']['variant_bindings']:
 v=source['variants'][binding['variant_id']];unit=defs[binding['unit']];a=unit['components']['attributes']['base'];n=v['native_enemy']['resolved'];mapping={'max_hp':'maxHp','atk':'atk','def':'def','mres':'magicResistance','move_speed':'moveSpeed','attack_interval':'baseAttackTime','mass_level':'massLevel'}
 for field,nfield in mapping.items():assert type(a[field]) in (int,float) and a[field]==n['attributes'][nfield]
 assert a['attack_speed_ratio']==n['attributes']['attackSpeed']/100 and unit['components']['lifecycle']['leak_loss']==n['lifePointReduce']
 assert exact(binding['native_reference'],v['native_reference'])
 variants.append({'id':binding['variant_id'],'unit':binding['unit'],'module':binding['module'],'stats':a,'abilities':[{'id':aid,'definition':defs[aid]} for aid in unit['components'].get('abilities',[])]})
roster=load(ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json');assert exact(scene['roster'],roster['manifest']['metadata']['roster']) and len(scene['roster'])==12
rdefs={d['id']:d for group in roster.values() if isinstance(group,list) for d in group if isinstance(d,dict) and 'id' in d}
assert all(exact(defs[eid],rdefs[eid]) for eid in scene['roster'])
restored=deepcopy(life);goal=restored['manifest']['metadata'].pop('goal_base_life_authoring');profile=restored['scenarioDraft']['metadata'].pop('runthrough_profile');restored['scenarioDraft']['resources']['life']=deepcopy(scene['resources']['life']);assert exact(restored,p)
assert type(goal['selected_initial']) is int and goal['selected_initial']==goal['selected_capacity']==99999 and exact(profile['fixed12'],scene['roster']) and profile['public_commands_sha256']==sha(C)
aliases={};deploys=[]
for c in cmd:
 assert type(c['at']) is int and c['at']>=0
 if c['action']=='deploy':
  eid=c.get('entity',c.get('definition'));assert eid in scene['roster'];aliases[c['alias']]=eid;deploys.append(eid);tile=scene['map']['tiles'][c['row']*scene['map']['cols']+c['col']];mask={'ground':1,'highland':2,'high':2,'any':3}[defs[eid]['components']['deployable']['terrain']];assert tile['buildableType']&mask
 elif c['action']=='skill':assert c['source'] in aliases and c['ability'] in defs[aliases[c['source']]]['components']['abilities']
 else:assert c['action']=='withdraw' and c['source'] in aliases
assert len(cmd)==28 and set(deploys)==set(scene['roster'])
negative=[]
for label,edit in [('active_branch',lambda n:n['waves'][0]['fragments'][0]['actions'][0].update(key='bsnake_flame')),('hard_payload',lambda n:n['hardPredefines']['characterCards'].update(foreign={'alias':'x'}))]:
 dirty=deepcopy(native);edit(dirty)
 try:compose(dirty,'level_main_08-16',{}, {},inactive_profile={'native_branches':dirty['branches'],'reason':'peer mutation','source_consumer_documents':[p]})
 except ValueError:negative.append(label)
 else:raise AssertionError(label+' accepted')
reg=providers();program=Compiler(providers=reg).compile(p);sim=Engine.create(program,providers=reg);sim.advance(7);pin=write_ordered(OUT/'source7.cp.json',sim.checkpoint());rr=Engine.restore(program,load_bound(OUT/'source7.cp.json',pin),providers=reg);sim.advance(8);rr.advance(8);head=replay(program,sim.export_replay(),providers=reg);assert sim.checkpoint()==rr.checkpoint()==head.checkpoint()
(OUT/'capture15.json').write_text(json.dumps({'checkpoint':sim.checkpoint(),'snapshot':sim.snapshot(),'events':thaw(tuple(sim.session.events)),'replay':sim.export_replay()},ensure_ascii=False,indent=2),encoding='utf8')
after=guards();assert before==after
old=load(ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.json');olddefs={d['id']:d for d in old['definitions']};changed=[key for key,value in defs.items() if key not in olddefs or not exact(value,olddefs[key])]
parent=defs['buff/ch8/source/dragon_fire'];assert parent['lifetime']=={'rule':'rule/ch8/dragon_fire/dynamic_rate','parameters':{},'count_when_inactive':True}
assert defs['rule/ch8/dragon_fire/dynamic_rate']['contract']=='buff.lifetime_rate' and defs['rule/ch8/dragon_fire/dynamic_rate']['implementation']['provider']=='reference.c8.dynamic_buff_rate'
assert all(exact(defs[b['unit']],olddefs[b['unit']]) for b in p['manifest']['metadata']['variant_bindings'])
report={'passed':True,'core':implementation_digest(),'package_sha':sha(P),'overlay_sha':sha(L),'commands_sha':sha(C),'variants':variants,'actions':actions,'births':births,'life_only_type_exact':True,'fixed12_exact':True,'static_28_command_bindings':True,'negative_cases':negative,'ordered_cp_sha':pin,'cp_head_equal':True,'source_input_reference_admitted':True,'complete_source_mechanisms':False,'previous_dynamic_remaining_gap_closed':True,'dynamic_source_independent_receipt':{'path':'validation/campaign/chapter08_dynamic_burn_independent_v4/freeze.json','sha':sha(ROOT/'validation/campaign/chapter08_dynamic_burn_independent_v4/freeze.json'),'scope':'7 source/reference cases new7e76/source00f13; four relevant missingperiodic/max/previouscounting generic gaps independently repaired and actual26 separatefreeze.'},'changed_definition_ids_vs_old9ad_input':changed,'all_five_actor_definitions_unchanged':True,'remaining_limits':['Native marker selector/filter listener exactbody not proven; declared executable reference rules retained, no actual unsupported op in compiledclosure','Native body/client comparison and version discrepancies remain pending; reference geometry/animation/capture policies explicitly selected','All12 actualdeployments/28command outcomes and wholecontinuous/CP/head/numeric ledger require current fullrun; not inferred from static plan','Otherfourenemy behavior independentproofs belong their recordedoldercore scope; current7e76 closure/definitions/prefix rechecked without relabelling oldercaptures'],'policies':'Native inactive branch asset retained with no selected consumer advance trigger. Source-derived Talula four-Prefab keyed skill overlay retained with only DanceFire40/init160 override. Dynamic parent Attr26 now nominalrateclock, with explicit .001..1000clamp. Geometry/animation/clock interpretations remain explicit replaceable reference profiles. FOUR_STAR runes preserved as NORMAL inactive.','scope':'Read-only new7e76/sourcev5 input/dependency/consumer field bindings, same28commands lifeonly and short native CP7->15/head. Dynamic remaining gap closed by actualnewsource7 cases/generic26, no whole/numeric-all/client approval or actualall12 guarantee. Source metadata pending/draftFalse retained as historical description, not automatic refusal.','guards_start':before,'guards_end':after,'guards_equal':True}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(sha(OUT/'verification.json'))

