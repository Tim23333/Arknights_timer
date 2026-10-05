"""Fresh full source-owned pillar chain fixture on f48; author tests not imported."""
from tools.chapter09_depletion_peer_joint.fixture import ROOT,CAND,CORE,REPORT,LOG,guard,START,sha,REG as primitive_REG
import json
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
assert implementation_digest()==CORE
from tools.chapter09_pillar_lifecycle_v1.build import providers
REG=providers();MODULE=ROOT/'packages/campaign/chapter09_consumers/pillar_lifecycle_v1/module.v1.json';BUILD=ROOT/'tools/chapter09_pillar_lifecycle_v1/build.py';SOURCE_LOCKS={str(p):sha(p) for p in [MODULE,BUILD]}

def actor(name,side=1,motion=1,category=1):return {'id':'unit/peer/pillar/'+name,'kind':'entity','tags':[name],'components':{'attributes':{'base':{'max_hp':24689,'atk':13111,'def':863,'mres':47,'move_speed':0,'block_cost':1}},'resources':{'hp':{'role':'health','initial':24689,'capacity':24689}},'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':4 if category==2 else 1 if side==0 else 2},'spatial':{'motion_mode':int(motion==2)},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}

def scene(direction='right',outside=False):
 p=json.loads(MODULE.read_bytes());p['manifest']['requires']=['preset/ark_standard'];d={'right':(0,1),'left':(0,-1),'up':(-1,0),'down':(1,0)}[direction];origin=(4,4);casterpos=(4-d[0],4-d[1]);casterpos=(4-2*d[0],4-2*d[1]) if outside else casterpos
 caster=actor('caster',0);caster['components']['abilities']=['ability/peer/pillar_hit'];p['entities'].append(caster);p['selectors']=[{'id':'selector/peer/pillar','kind':'selector','region':{'type':'all'},'filters':[{'tag':'pillar'}],'limit':1}];p['abilities'].append({'id':'ability/peer/pillar_hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/pillar','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
 p['scenarioDraft']={'id':'scene/peer/fullpillar/'+direction,'ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':9},'initialEntities':[{'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':4,'col':4}},{'definition':caster['id'],'instanceAlias':'caster','position':{'row':casterpos[0],'col':casterpos[1]}}],'commands':[{'at':13,'action':'skill','source':'caster','ability':'ability/peer/pillar_hit'},{'at':83,'action':'skill','source':'caster','ability':'ability/peer/pillar_hit'}]}
 slots=[('ground',1,1,1,(4+d[0],4+d[1])),('fly',1,2,1,(4+2*d[0],4+2*d[1])),('player',0,1,1,origin),('trap',0,1,2,(4+2*d[0],4+2*d[1])),('off_axis',1,1,1,(1,1))]
 for name,side,motion,category,pos in slots:
  a=actor(name,side,motion,category);p['entities'].append(a);p['scenarioDraft']['initialEntities'].append({'definition':a['id'],'instanceAlias':name,'position':{'row':pos[0],'col':pos[1]}})
 return p
