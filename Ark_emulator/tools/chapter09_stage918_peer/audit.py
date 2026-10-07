"""Independent strict native source918 input checks; no author verifier fixtures."""
import sys,json,hashlib,math
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_duspfr_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter09_stage_assembly_v1.providers import providers
CORE='2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0';assert implementation_digest()==CORE
PACKAGE=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v1.life99999.json';SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/source.plan.v1.json';ROSTER=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';COMMANDS=ROOT/'scenarios/campaign/chapter09/level_main_09-16/public_plan_v1_finite/commands.json';PLAN=COMMANDS.parent/'plan.json';REPORT=ROOT/'validation/campaign/chapter09_stage918_peer';LOG=Path('E:/ArkSimLogs/runs/chapter09_stage918_peer');REG=providers();STAGE='level_main_09-16'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 if isinstance(a,float) and a==b==0:return math.copysign(1,a)==math.copysign(1,b)
 return a==b

def guard():
 assert implementation_digest()==CORE;assert sha(PACKAGE)=='a13a221720d9a542320fbe16a1c5ad135cec8bd23254e2fc1296b3dddc879f6d';assert sha(COMMANDS)=='90075a3cd677566c919553633e58f3c41ace8624fbdae53cadea6fe7a2ba6a2e'
 package=json.loads(PACKAGE.read_bytes())
 for name,value in package['manifest']['metadata']['source_locks'].items():assert sha(Path(name))==value
 files=[PACKAGE,SOURCE,ROSTER,COMMANDS,PLAN,ROOT/'tools/chapter09_stage_assembly_v1/build_918.py',ROOT/'tools/chapter09_stage_assembly_v1/build_commands_918.py',ROOT/'tools/chapter09_stage_assembly_v1/providers.py',ROOT/'tools/chapter09_demolition_v2/build.py',ROOT/'tools/chapter09_duspfr_v1/build.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts];return {str(p):sha(p) for p in files}
START=guard()
def audit(package):
 source=json.loads(SOURCE.read_bytes());stage=source['stages'][STAGE];native=stage['native_document'];scene=package['scenarioDraft'];meta=package['manifest']['metadata'];defs={d['id']:d for d in package['definitions']};assert len(defs)==len(package['definitions'])==308
 assert exact(meta['native_predefines'],native['predefines']) and exact(meta['native_hard_predefines'],native['hardPredefines']);assert exact(meta['native_options'],native['options']);assert meta['native_source_digest']==hashlib.sha256(json.dumps(native,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 assert set(native['predefines'])==set(native['hardPredefines'])=={'characterInsts','tokenInsts','characterCards','tokenCards'};assert native['predefines']['characterInsts']==native['predefines']['characterCards']=={};assert all(type(v)is dict and not v for v in native['hardPredefines'].values());assert meta['difficulty_profile'].startswith('NORMAL1')
 assert scene['parameters']['deploy_capacity']==native['options']['characterLimit']==8 and type(scene['parameters']['deploy_capacity'])is int;assert exact(scene['resources']['life'],{'initial':99999,'capacity':99999});assert exact(scene['resources']['dp'],{'initial':12,'capacity':99,'recovery_rate':1.0,'recovery':{'mode':'periodic','interval_seconds':1.0}});assert scene['seed']==native['randomSeed'];assert exact(scene['metadata']['native_options'],native['options'])
 roster=json.loads(ROSTER.read_bytes());rdefs={d['id']:d for d in roster['definitions']};assert exact(scene['roster'],roster['manifest']['metadata']['roster']) and len(scene['roster'])==12;HP={}
 for uid in scene['roster']:
  assert exact(defs[uid],rdefs[uid]);cfg=defs[uid]['metadata']['config'];assert exact({k:cfg[k] for k in ['elite_phase','level','mastery','potential','potential_rank','trust_percent','equipment_id','equipment_level','skill_level_index']},{'elite_phase':2,'level':70,'mastery':3,'potential':1,'potential_rank':0,'trust_percent':100,'equipment_id':None,'equipment_level':0,'skill_level_index':9});assert not defs[uid]['components'].get('equipment');HP[uid]=defs[uid]['components']['attributes']['base']['max_hp']
 rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0]);mp=scene['map'];assert (mp['rows'],mp['cols'])==(rows,cols);build={'NONE':0,'MELEE':1,'RANGED':2,'ALL':3};passing={'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3};cells={}
 for ri,line in enumerate(native['mapData']['map']):
  for ci,index in enumerate(line):
   raw=native['mapData']['tiles'][index];expected={'tileKey':raw['tileKey'],'buildableType':build[raw['buildableType']],'passableMask':passing[raw['passableMask']],'heightType':raw['heightType'],'blackboard':raw['blackboard'],'effects':raw['effects']};assert exact(mp['tiles'][ri*cols+ci],expected)
   if raw['blackboard']:
    cells[str(ri)+':'+str(ci)]={r['key']:r['value'] for r in raw['blackboard']};assert exact(mp['tile_cell_mechanics'][str(ri)+':'+str(ci)]['expected_blackboard'],cells[str(ri)+':'+str(ci)])
 assert set(mp['tile_cell_mechanics'])==set(cells) and len(cells)==4
 rawinst=native['predefines']['tokenInsts'];initial=scene['initialEntities'];assert len(rawinst)==len(initial)==3;assert len({x['alias'] for x in rawinst})==1
 for i,(raw,inst) in enumerate(zip(rawinst,initial)):
  assert exact(inst['parameters']['native_instance'],raw);assert inst['parameters']['source_record_index']==i and type(inst['parameters']['source_record_index'])is int;assert inst['parameters']['raw_alias']==raw['alias'];assert inst['registration_key']==STAGE+'/tokenInsts/'+str(i);assert inst['instanceAlias'] is None;assert inst['active'] is (not raw['hidden']);assert exact(inst['position'],{'row':rows-1-raw['position']['row'],'col':raw['position']['col']});assert inst['facing']==raw['direction'].lower();assert inst['definition']=='unit/ch9/pillar/body'
 cards=native['predefines']['tokenCards'];assert len(cards)==1;binding=scene['metadata']['native_card_bindings'][0];assert exact(binding['native_card'],cards[0]);assert cards[0]['initialCnt']==2 and type(cards[0]['initialCnt'])is int;assert scene['cards']==[binding['definition']];assert exact(scene['resources'][binding['stock_resource']],{'initial':2,'capacity':2})
 assert exact(scene['metadata']['native_predefines'],native['predefines']);runes=scene['metadata']['rune_policy'];assert len(runes)==len(native['runes']);masks={'NONE':0,'NORMAL':1,'FOUR_STAR':2,'EASY':4,'SIX_STAR':8,'ALL':15}
 for raw,entry in zip(native['runes'],runes):assert exact(entry['raw'],raw) and entry['difficulty_bit']==1 and entry['active'] is bool(masks[raw['difficultyMask']]&1);assert entry['active'] is False
 counts={};routes=set();controls=[]
 def route(raw):
  out=deepcopy(raw)
  for field in ['startPosition','endPosition']:out[field]={'row':rows-1-raw[field]['row'],'col':raw[field]['col']}
  out['checkpoints']=out.get('checkpoints') or []
  for cp in out['checkpoints']:
   if cp.get('position') is not None:cp['position']={'row':rows-1-cp['position']['row'],'col':cp['position']['col']}
  if out['motionMode']=='E_NUM':out['motionMode']='WALK'
  return out
 assert len(native['routes'])==25;assert len(scene['timeline']['waves'])==len(native['waves'])
 for wi,(nw,mw) in enumerate(zip(native['waves'],scene['timeline']['waves'])):
  for nk,mk in [('preDelay','pre_delay_seconds'),('postDelay','post_delay_seconds'),('maxTimeWaitingForNextWave','max_wait_seconds')]:assert exact(nw[nk],mw[mk])
  assert len(nw['fragments'])==len(mw['fragments'])
  for fi,(nf,mf) in enumerate(zip(nw['fragments'],mw['fragments'])):
   assert exact(nf['preDelay'],mf['pre_delay_seconds']);assert len(nf['actions'])==len(mf['actions'])
   for ai,(raw,action) in enumerate(zip(nf['actions'],mf['actions'])):
    assert exact(raw,action['metadata']['native_action']);assert exact(raw['count'],action['count']);assert exact(raw['preDelay'],action['delay_seconds']);assert exact(raw['interval'],action['interval_seconds']);assert exact(raw['managedByScheduler'],action['managed']);assert type(raw['dontBlockWave'])is bool and action['blocks_wave'] is (not raw['dontBlockWave']);assert exact(raw['blockFragment'],action['blocks_fragment']);assert raw['randomType']==raw['refreshType']=='ALWAYS';assert raw['hiddenGroup'] is raw['randomSpawnGroupKey'] is raw['randomSpawnGroupPackKey'] is None;assert raw['forceBlockWaveInBranch'] is False;assert raw['isUnharmfulAndAlwaysCountAsKilled'] is False
    if raw['actionType']=='SPAWN':
     assert action['kind']=='spawn';vid=next(v for v in stage['variant_ids'] if source['variants'][v]['native_reference']['id']==raw['key']);unit=meta['variant_bindings'][vid]['unit'];assert action['spawn']['definition']==unit;expected=route(native['routes'][raw['routeIndex']]);assert exact(action['spawn']['route'],expected);assert exact(action['spawn']['position'],expected['startPosition']);assert action['spawn']['parameters']=={'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_route_index':raw['routeIndex']};assert action['spawn']['instanceAlias']==f'{STAGE}/w{wi}/f{fi}/a{ai}';assert exact(action['spawn']['placement']['offset'],{'row':-expected['spawnOffset']['y'],'col':expected['spawnOffset']['x']});assert exact(action['spawn']['placement']['random_range'],{'row':expected['spawnRandomRange']['y'],'col':expected['spawnRandomRange']['x']});counts[unit]=counts.get(unit,0)+raw['count'];routes.add(raw['routeIndex'])
    else:
     assert raw['actionType']=='PREVIEW_CURSOR' and action['kind']=='control';ctrl=defs[action['definition']];assert exact(ctrl['metadata']['native_action'],raw);assert ctrl['steps'][0]['kind']=='effects';controls.append(action['definition'])
 assert sum(counts.values())==34 and len(controls)==2 and len(routes)==23
 numeric_kind_encodings=[]
 for vid,binding in meta['variant_bindings'].items():
  raw=source['variants'][vid];assert exact(binding['native_reference'],raw['native_reference']);unit=defs[binding['unit']];attr=raw['native_enemy']['resolved']['attributes'];base=unit['components']['attributes']['base'];assert exact(base['max_hp'],attr['maxHp']);assert exact(unit['components']['resources']['hp']['initial'],attr['maxHp'])
  for sk,mk in [('atk','atk'),('def','def'),('magicResistance','mres'),('moveSpeed','move_speed'),('baseAttackTime','attack_interval'),('massLevel','mass_level')]:
   assert not isinstance(base[mk],bool) and base[mk]==attr[sk]
   if type(base[mk])!=type(attr[sk]):numeric_kind_encodings.append({'unit':binding['unit'],'field':mk,'native':attr[sk],'native_kind':type(attr[sk]).__name__,'model':base[mk],'model_kind':type(base[mk]).__name__,'numeric_value_equal':True})
  assert base['attack_speed_ratio']==attr['attackSpeed']*.01
 status=defs['rule/ch9/demolition/push']['parameters']['status_definitions'];buffs={k:{'selection_flags':deepcopy(v.get('selection_flags',{}))} for k,v in defs.items() if v['kind']=='buff'};assert exact(status,buffs) and len(status)==85
 commands=json.loads(COMMANDS.read_bytes());assert len(commands)==42;assert commands==sorted(commands,key=lambda x:x['at']);deploys=[c for c in commands if c['action']=='deploy'];assert {c['entity'] for c in deploys if c['entity'] in scene['roster']}==set(scene['roster']);assert len([c for c in deploys if c['entity']==scene['cards'][0]])==2
 for c in commands:
  assert type(c['at'])is int and c['at']>=0
  if c['action']=='deploy':assert set(c)=={'at','action','entity','row','col','facing','alias'};assert c['entity'] in defs;assert type(c['row'])is type(c['col'])is int;assert c['facing'] in ['up','down','left','right'];assert 0<=c['row']<rows and 0<=c['col']<cols
  elif c['action']=='withdraw':assert set(c)=={'at','action','source'}
  else:assert c['action']=='skill' and set(c)<= {'at','action','source','ability','payload'} and c['ability'] in defs
 return {'type_exact_native_metadata_options_actions_routes_registrations_tiles':True,'definitions':308,'source_births':34,'native_routes':25,'used_routes':23,'preview_controls':controls,'roster12_HP':HP,'native_slots':8,'native_DP':12,'only_life_override':99999,'native_card_stock':2,'blackboard_cells':cells,'complete_status_Buff_closure':85,'numeric_scalar_kind_encodings':numeric_kind_encodings,'commands':42,'client_verified':False,'whole_stage':False}
