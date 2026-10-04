"""Fresh content peer inputs on v9; frozen content/provider imports only."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_foundation_v9_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.selection import DEFAULT_STATE
CORE='56f380fab9715b8edcb589b2c3fc3863d740cb149ab31e19b3f6fe3a1720fcf6';assert implementation_digest()==CORE
from tools.chapter09_pillar_v1.build_payload import providers as pillar_providers
from tools.chapter09_coupled_v2.build_v2 import providers as coupled_providers
from tools.chapter09_rock_gargoyle.build_v1 import providers as rock_providers,build as rock_build
assert implementation_digest()==CORE
REG={**pillar_providers(),**coupled_providers(),**rock_providers()}
PILLAR=ROOT/'packages/campaign/chapter09_consumers/pillars/collapse.payload.v1.json';COUPLED=ROOT/'packages/campaign/chapter09_consumers/coupled_v2/duholy_dushdo.module.v2.json';REPORT=ROOT/'validation/campaign/chapter09_content_peer_v9';LOG=Path('E:/ArkSimLogs/runs/chapter09_content_peer_v9')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
FROZEN=[PILLAR,COUPLED,ROOT/'tools/chapter09_pillar_v1/build_payload.py',ROOT/'tools/chapter09_coupled_v2/build_v2.py',ROOT/'tools/chapter09_rock_gargoyle/build_v1.py']
def guard():
 assert implementation_digest()==CORE
 out={str(p):sha(p) for p in FROZEN}
 for p in [PILLAR,COUPLED]:
  meta=json.loads(p.read_bytes())['manifest']['metadata'];assert all(sha(Path(f))==h for f,h in meta['source_locks'].items())
 out.update({str(p):sha(p) for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')});return out
START=guard()
def merge(*parts):
 p={'schemaVersion':2,'manifest':{'id':'package/content_peer/v9','requires':['preset/ark_standard']}}
 for part in parts:
  for k,v in part.items():
   if k in ('schemaVersion','manifest','scenarioDraft'):continue
   p.setdefault(k,[]).extend(deepcopy(v))
 return p

def actor(id,side=1,motion=1,category=1):return {'id':'unit/peer/'+id,'kind':'entity','tags':['peer',id,'enemy' if side==1 else 'player'],'components':{'attributes':{'base':{'max_hp':17777,'atk':17777,'def':731,'mres':43,'attack_speed_ratio':1.3,'block_count':0,'move_speed':0,'block_cost':1}},'resources':{'hp':{'role':'health','capacity':17777,'initial':17777}},'selection_state':{'side':side,'motion':motion,'category':category,'unit_type':2 if side==1 else 1},'spatial':{'motion_mode':1 if motion==2 else 0},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}

def pillar_scene(direction='right',mode='normal'):
 p=merge(json.loads(PILLAR.read_bytes()));origin=(3,3);d={'right':(0,1),'left':(0,-1),'up':(-1,0),'down':(1,0)}[direction];cells=[(3+d[0],3+d[1]),(3+2*d[0],3+2*d[1])]
 p['scenarioDraft']={'id':'scene/peer/pillar/'+direction+'/'+mode,'ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':8},'initialEntities':[{'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':3,'col':3}}],'commands':[{'at':0,'action':'skill','source':'pillar','ability':'ability/ch9/pillar/collapse_'+direction}]}
 slots=[('ground',1,1,1,cells[0]),('flying',1,2,1,cells[1]),('off_axis',1,1,1,(2,2)),('player',0,1,1,(3,3))]
 for alias,side,motion,category,pos in slots:
  a=actor(alias,side,motion,category);p['entities'].append(a);p['scenarioDraft']['initialEntities'].append({'definition':a['id'],'instanceAlias':alias,'position':{'row':pos[0],'col':pos[1]}})
 if mode in ('free','invisible','camo'):
  ground=next(x for x in p['entities'] if x['id']=='unit/peer/ground');ground['components']['selection_state'].update({'target_free':True} if mode=='free' else {'abnormal_flags':[9]} if mode=='invisible' else {'camouflage':True})
 if mode=='wall':
  tiles=[{'tileKey':'tile_floor','passableMask':1,'buildableType':1,'heightType':0} for _ in range(56)];r,c=cells[1];tiles[r*8+c]={'tileKey':'tile_wall','passableMask':0,'buildableType':0,'heightType':1};p['scenarioDraft']['map']['tiles']=tiles
 if mode=='late':
  p['scenarioDraft']['initialEntities'][1]['position']={'row':1,'col':6};p['entities'][2]['components']['abilities'].append('ability/peer/late_move');p['abilities'].append({'id':'ability/peer/late_move','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':cells[0][0],'col':cells[0][1]}}}]});p['scenarioDraft']['commands'].append({'at':44,'action':'skill','source':'ground','ability':'ability/peer/late_move'})
 return p

def gargoyle_scene():
 pillar=json.loads(PILLAR.read_bytes());trait=next(x for x in pillar['buffs'] if x['id']=='buff/ch9/pillar/trait');garg=rock_build('enemy_1172_dugago',pillar_trait_buff=trait['id'],dependency_definitions=[trait]);assert garg['manifest']['metadata']['required_runtime']==CORE
 p=merge(pillar,garg);controller=actor('controller',0);controller['components']['abilities']=['ability/peer/kill','ability/peer/sethp'];p['entities'].append(controller);p['selectors'].append({'id':'selector/peer/garg','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 for name,e in [('kill',{'op':'damage','damage_type':'true','scale':1}),('sethp',{'op':'modify_resource','resource':'hp','value':0,'parameters':{'operation':'damage'}})]:p['abilities'].append({'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/garg','timeline':[{'at':0,'effect':e}]})
 p['scenarioDraft']={'id':'scene/peer/pillar_garg','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':8},'initialEntities':[{'definition':'unit/ch9/pillar/body','instanceAlias':'pillar','position':{'row':3,'col':3}},{'definition':garg['entities'][0]['id'],'instanceAlias':'garg','position':{'row':3,'col':4}},{'definition':controller['id'],'instanceAlias':'controller','position':{'row':0,'col':0}}],'commands':[]};return p

def coupled_scene(holy_positions=((3,3),),shadow_positions=((3,3.7),),player=(2.2,3),guard_block=0):
 p=merge(json.loads(COUPLED.read_bytes()));h=p['entities'][0]['id'];s=p['entities'][1]['id'];target=actor('observer',0);target['components']['attributes']['base']['block_count']=guard_block;target['components']['abilities']=['ability/peer/move_observer'];p['entities'].append(target);p['abilities'].append({'id':'ability/peer/move_observer','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':0,'col':0}}}]})
 initial=[{'definition':h,'instanceAlias':'holy'+str(i),'position':{'row':x[0],'col':x[1]}} for i,x in enumerate(holy_positions)]+[{'definition':s,'instanceAlias':'shadow'+str(i),'position':{'row':x[0],'col':x[1]}} for i,x in enumerate(shadow_positions)]+[{'definition':target['id'],'instanceAlias':'observer','position':{'row':player[0],'col':player[1]}}]
 p['scenarioDraft']={'id':'scene/peer/coupled','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':8},'initialEntities':initial,'commands':[]};return p

def coupled_blocked_scene(paired=False,leave_at=None,unblock_at=None):
 p=coupled_scene(holy_positions=((3,3.6),) if paired else ((0,7),),shadow_positions=((3,3),),player=(3,3),guard_block=1);observer=next(e for e in p['entities'] if e['id']=='unit/peer/observer');observer['components']['deployable']={'base_cost':1,'terrain':'ground','capacity':1,'cooldown_seconds':0};p['scenarioDraft']['initialEntities']=[x for x in p['scenarioDraft']['initialEntities'] if x['instanceAlias']!='observer'];p['scenarioDraft']['roster']=['unit/peer/observer'];p['scenarioDraft']['resources']={'dp':{'initial':10,'capacity':99}};p['scenarioDraft']['commands']=[{'at':0,'action':'deploy','entity':'unit/peer/observer','alias':'observer','row':3,'col':3}]
 shadow=next(x for x in p['scenarioDraft']['initialEntities'] if x['instanceAlias']=='shadow0');shadow['route']={'motionMode':'WALK','startPosition':{'row':3,'col':3},'endPosition':{'row':3,'col':6},'checkpoints':[]}
 if leave_at is not None:
  holy=next(e for e in p['entities'] if '/duholy/' in e['id']);holy['components']['abilities'].append('ability/peer/holy_leave');p['abilities'].append({'id':'ability/peer/holy_leave','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':0,'col':7}}}]});p['scenarioDraft']['commands'].append({'at':leave_at,'action':'skill','source':'holy0','ability':'ability/peer/holy_leave'})
 if unblock_at is not None:p['scenarioDraft']['commands'].append({'at':unblock_at,'action':'skill','source':'observer','ability':'ability/peer/move_observer'})
 return p
