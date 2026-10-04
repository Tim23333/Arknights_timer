"""Independent bounded cell override fixtures; frozen business modules only."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_cell_fields_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
CORE='11b414e7b4ddbff8c2fcd1689655b1c9c486047ae805bf79eda27417b5759899';assert implementation_digest()==CORE
from tools.chapter09_pillar_v1.bigforce import providers as force_registry,profile as force_profile
from tools.chapter08_environment.policies_v1 import providers as infection_registry
from tools.chapter09_pillar_v1.registration import registrations,resolve_reference
REG={**force_registry(),**infection_registry()};assert implementation_digest()==CORE
BASE=ROOT/'packages/campaign/chapter09_consumers/pillars';FORCE=BASE/'bigforce.module.v1.json';MAPS=BASE/'native_maps.profile.v1.json';INFECT=ROOT/'packages/campaign/chapter08_consumers/environment/infection.module.v3.json';NATIVE=ROOT/'packages/campaign/chapter09_source_prepare/source.plan.v1.json';REPORT=ROOT/'validation/campaign/chapter09_cell_fields_peer';LOG=Path('E:/ArkSimLogs/runs/chapter09_cell_fields_peer')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE
 files=[FORCE,MAPS,INFECT,NATIVE,ROOT/'tools/chapter09_pillar_v1/bigforce.py',ROOT/'tools/chapter09_pillar_v1/build_map_profile.py',ROOT/'tools/chapter09_pillar_v1/registration.py',ROOT/'tools/chapter08_environment/policies_v1.py'];out={str(p):sha(p) for p in files}
 for p in [FORCE,INFECT]:assert all(sha(Path(f))==h for f,h in json.loads(p.read_bytes())['manifest']['metadata']['source_locks'].items())
 meta=json.loads(MAPS.read_bytes());assert meta['source_sha']==sha(NATIVE);assert meta['builder_sha']==sha(ROOT/'tools/chapter09_pillar_v1/build_map_profile.py')
 out.update({str(p):sha(p) for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')});return out
START=guard()
def package():
 p={'schemaVersion':2,'manifest':{'id':'package/peer/cell_fields','requires':['preset/ark_standard']}}
 for source in [FORCE,INFECT]:
  for k,v in json.loads(source.read_bytes()).items():
   if k not in ('schemaVersion','manifest'):p.setdefault(k,[]).extend(deepcopy(v))
 return p

def actor(name,side=0,motion=1,category=1):return {'id':'unit/peer/'+name,'kind':'entity','tags':['peer',name,'player' if side==0 else 'enemy'],'components':{'attributes':{'base':{'max_hp':54321,'atk':517,'def':913,'mres':61,'base_force_level':5.25,'attack_speed_ratio':1.4}},'resources':{'hp':{'role':'health','initial':54321,'capacity':54321}},'spatial':{'motion_mode':int(motion==2)},'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/leave']}}

def synthetic():
 p=package();tiles=[{'tileKey':'tile_road','buildableType':1,'passableMask':3,'heightType':0,'blackboard':None,'effects':None} for _ in range(12)];tiles[6]['blackboard']=[{'key':'base_force_level','value':1.0,'valueStr':None}];ip=json.loads(INFECT.read_bytes())['manifest']['metadata']['tile_profile'];tiles[11]['blackboard']=deepcopy(ip['expected_blackboard'])
 map_={'rows':3,'cols':4,'tiles':tiles,'tile_cell_mechanics':{'1:2':force_profile(),'2:3':ip}};p.setdefault('abilities',[]).append({'id':'ability/peer/leave','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':0,'col':0}}}]});initial=[]
 for name,side,motion,category,pos in [('ground',0,1,1,(1,2)),('fly',0,2,1,(1,2)),('enemy',1,1,1,(1,2)),('mechanism',0,1,2,(1,2)),('infected',0,1,1,(2,3)),('infection_fly',0,2,1,(2,3)),('plain',0,1,1,(1,3))]:
  a=actor(name,side,motion,category);p['entities'].append(a);initial.append({'definition':a['id'],'instanceAlias':name,'position':{'row':pos[0],'col':pos[1]}})
 p['scenarioDraft']={'id':'scene/peer/cell_fields','ruleset':'ruleset/ark_standard','map':map_,'initialEntities':initial,'commands':[{'at':2,'action':'skill','source':'ground','ability':'ability/peer/leave'},{'at':2,'action':'skill','source':'infected','ability':'ability/peer/leave'}]};return p
