import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate';CORE='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.build_campaign_runthrough_input import apply
assert implementation_digest()==CORE
OUT=ROOT/'validation/campaign/chapter02_03_refjoin_v1';PACK=ROOT/'packages/campaign/chapter02_03_refjoin_v1';INPUT=ROOT/'scenarios/campaign/chapter02_03_refjoin_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf8',newline='') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
FILES=[Path(__file__),ROOT/'tools/build_campaign_runthrough_input.py']+list((RUNTIME/'ark_sim').rglob('*.py'))+list((RUNTIME/'ark_sim').rglob('*.json'))
pins={}
def inspect_locks(value):
 if isinstance(value,dict):
  for name,expected in value.get('source_locks',{}).items():
   path=Path(name)
   if not path.is_absolute():
    options=[ROOT/path,ROOT.parent/path]
    path=next((candidate for candidate in options if candidate.is_file()),options[0])
   actual=sha(path);assert actual==expected,(name,expected,actual);pins[str(path)]=actual;FILES.append(path)
  for key,item in value.items():
   if key!='source_locks':inspect_locks(item)
 elif isinstance(value,list):
  for item in value:inspect_locks(item)
def guard():return {str(p):sha(p) for p in sorted(set(FILES))}
STAGES=[('02-10','packages/campaign/chapter02_stage_models/level_main_02-10.m48.combat_guard.reference_model.json','packages/campaign/runthrough/level_main_02-10.m48.combat_guard.life99999.json','scenarios/campaign/chapter02/02-10/commands.runthrough_exploratory_v1.json',36,12),('03-08','packages/campaign/chapter03_stage_models/level_main_03-08.m56.reference_model.json','packages/campaign/runthrough/level_main_03-08.m54.life99999.json','scenarios/campaign/chapter03/03-08/commands.runthrough_v1.json',63,8)]
for stage,parent,oldlife,commands,births,variants in STAGES:
 FILES.extend([ROOT/parent,ROOT/oldlife,ROOT/commands]);inspect_locks(read(ROOT/parent))
for chapter in ['02','03']:FILES.append(ROOT/('packages/campaign/chapter'+chapter+'_sources/native.reference.json'))
BEFORE=guard();RESULT=[]
for stage,parent,oldlife,commands,births,variants in STAGES:
 p=read(ROOT/parent);old=read(ROOT/oldlife);scene=p['scenarioDraft'];defs={d['id']:d for d in p['definitions']};cmds=read(ROOT/commands)
 assert p['definitions']==old['definitions']
 for k in scene:
  if k not in ['id','metadata','resources']:assert scene[k]==old['scenarioDraft'][k],k
 assert scene['resources']['dp']==old['scenarioDraft']['resources']['dp']
 assert scene['resources']['life']=={'initial':3,'capacity':3}
 actions=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions']]
 counts=Counter();controls=Counter();route_values=[]
 for a in actions:
  raw=a['metadata']['native_action'];assert a['count']==raw['count'] and a['managed']==raw['managedByScheduler'] and a['blocks_fragment']==raw['blockFragment']
  assert a['delay_seconds']==raw['preDelay'] and a['interval_seconds']==raw['interval']
  if a['kind']=='spawn':counts[a['spawn']['definition']]+=a['count'];route_values.append(a['spawn']['route'])
  else:controls[raw['actionType']]+=a['count']
 assert sum(counts.values())==births and len(counts)==variants and len(scene['roster'])==12 and scene['initialEntities']==[]
 hp={k:defs[k]['components']['resources']['hp']['initial'] for k in counts}
 legality=[];aliases={}
 roster=[x['definition'] if isinstance(x,dict) else x for x in scene['roster']]
 for c in cmds:
  verdict={'command':c,'schema_checked':True}
  if c['action']=='deploy':
   d=defs[c['definition']];assert c['definition'] in roster;aliases[c['alias']]=c['definition'];pos=c['position'];tile=scene['map']['tiles'][pos['row']*scene['map']['cols']+pos['col']];terrain=d['components']['deployable']['terrain'];assert tile['buildableType']==(1 if terrain=='ground' else 2);verdict['terrain_valid']=True
  elif c['action']=='skill':
   d=defs[aliases[c['source']]];aid=c['ability'];assert aid in d['components']['abilities'];ability=defs[aid];verdict.update(activation_mode=ability['activation']['mode'],auto_only=ability['activation'].get('parameters',{}).get('auto_only',False),expected_runtime_rejection=ability['activation'].get('parameters',{}).get('auto_only',False) or ability['activation']['mode']=='automatic')
  else:assert c['action']=='withdraw' and c['source'] in aliases
  legality.append(verdict)
 p['manifest']['id']+='/refjoin8fa';p['manifest']['metadata'].update(required_runtime=CORE,refjoin_parent_sha256=sha(ROOT/parent),refjoin_builder_sha256=sha(Path(__file__)),full_stage_executed=False,actual_client_verified=False,refjoin_scope='Frozen source definitions/scenario unchanged; new selected runtime identity. No old checkpoint migrated.')
 scene['id']+='/refjoin8fa';native=PACK/('level_main_'+stage+'.native_life.json');write(native,p)
 covered=apply(p,sha(native));assert covered['definitions']==old['definitions'];life=PACK/('level_main_'+stage+'.life99999.json');write(life,covered)
 cp=INPUT/(stage+'.commands.json');cp.parent.mkdir(parents=True,exist_ok=True)
 with cp.open('xb') as f:f.write((ROOT/commands).read_bytes())
 assert sha(cp)==sha(ROOT/commands)
 program=Compiler().compile(covered)
 RESULT.append({'stage':stage,'native_package':str(native),'life_package':str(life),'commands':str(cp),'births':dict(counts),'total_births':births,'variants':variants,'HP':hp,'routes':route_values,'controls':dict(controls),'runes':scene['metadata']['rune_policy'],'predefines':scene['initialEntities'],'map':{'rows':scene['map']['rows'],'cols':scene['map']['cols']},'roster':scene['roster'],'command_count':len(cmds),'command_legality':legality,'native_sha':sha(native),'life_sha':sha(life),'commands_sha':sha(cp),'program_fingerprint':program.fingerprint,'pending_model_gaps':p['manifest']['metadata'].get('pending_model_gaps',[]),'source_parent':parent,'source_parent_sha':sha(ROOT/parent),'old_life_sha':sha(ROOT/oldlife)})
AFTER=guard();assert BEFORE==AFTER
write(OUT/'preparation.json',{'core':CORE,'runtime':str(RUNTIME),'results':RESULT,'source_pins':pins,'guard_start':BEFORE,'guard_end':AFTER,'source_guard_equal':True,'full_stage_started':False,'old_checkpoints_consumed':False})
print(json.dumps({'report':str(OUT/'preparation.json'),'sha':sha(OUT/'preparation.json'),'stages':[{'stage':r['stage'],'births':r['total_births'],'variants':r['variants'],'commands':r['command_count']} for r in RESULT]}))
