"""Independent demolition fixture; frozen business builder only, no author fixtures."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_pillar_channel_joint_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from tools.chapter09_demolition_v1.build import build,providers,BODY,STOCK,BLAST
CORE='53ee67c10a664707d8b23bd1191bd5995085ed20cd92837bb8ab64c63f93ff7c';assert implementation_digest()==CORE
from tools.chapter09_pillar_lifecycle_v1.build import providers as pillar_providers
REG={**providers(),**pillar_providers()};REPORT=ROOT/'validation/campaign/chapter09_demolition_peer';LOG=Path('E:/ArkSimLogs/runs/chapter09_demolition_peer');HP=28361
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE
 files=[ROOT/'validation/campaign/chapter09_demolition_v1/freeze.v1.json',ROOT/'tools/chapter09_demolition_v1/build.py',ROOT/'packages/campaign/chapter09_source_prepare/predefines.native.v3.json',ROOT/'packages/campaign/chapter09_consumers/pillar_lifecycle_v1/module.v1.json',ROOT/'tools/chapter09_pillar_lifecycle_v1/build.py',ROOT/'tools/build_weedy_skill_recipe.py',ROOT/'ark_emulator/consts.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.parts]
 return {str(p):sha(p) for p in files}
START=guard()
def actor(name,side=1,motion=1,category=1,mass=4,flags=(),free=False,camo=False,profession=0):
 return {'id':'unit/peer/demolition/'+name,'kind':'entity','tags':[name],'components':{'attributes':{'base':{'max_hp':HP,'atk':0,'def':811,'mres':61,'mass_level':mass}},'resources':{'hp':{'initial':HP,'capacity':HP,'role':'health'}},'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':2 if side==1 else 1,'abnormal_flags':list(flags),'target_free':free,'camouflage':camo,'profession':profession},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
def scene(direction='right',pillar=False,mass=4):
 deps={d:'ability/ch9/pillar/collapse_'+d for d in ['up','down','left','right']} if pillar else None;p=build(pillar_abilities=deps);dr,dc={'right':(0,1),'left':(0,-1),'up':(-1,0),'down':(1,0)}[direction];target=(3+dr,3+dc);a=actor('enemy',mass=mass);p['entities'].append(a);initial=[{'definition':a['id'],'instanceAlias':'enemy','position':{'row':target[0],'col':target[1]}}]
 if pillar:
  mod=json.loads((ROOT/'packages/campaign/chapter09_consumers/pillar_lifecycle_v1/module.v1.json').read_bytes())
  for k in ['rules','buffs','abilities','entities']:p[k]+=deepcopy(mod.get(k,[]))
  initial.append({'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':target[0],'col':target[1]}})
 p['scenarioDraft']={'id':'scene/peer/demolition/'+direction+str(pillar),'ruleset':'ruleset/ark_standard','cards':[BODY],'parameters':{'deploy_capacity':0},'map':{'rows':8,'cols':10},'resources':{'dp':{'initial':37,'capacity':99},'life':{'initial':99999,'capacity':99999},STOCK:{'initial':2,'capacity':2}},'initialEntities':initial,'commands':[{'at':7,'action':'deploy','definition':BODY,'alias':'device','position':{'row':3,'col':3},'facing':direction}]};return p
