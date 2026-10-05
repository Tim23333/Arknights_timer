"""Independent dynamic native unbalance projection cases; no author fixtures."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_pillar_channel_joint_v3_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from tools.chapter09_demolition_v2.build import build,bind_status_definitions,providers,BODY,STOCK,PREFIX
CORE='4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4';assert implementation_digest()==CORE
FREEZE=ROOT/'validation/campaign/chapter09_demolition_v2/freeze.v2.json';REPORT=ROOT/'validation/campaign/chapter09_demolition_peer_v2';LOG=Path('E:/ArkSimLogs/runs/chapter09_demolition_peer_v2');REG=providers();HP=29413
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(FREEZE)=='fe5dee42766ba9658a13e86f5d7c7599effa126dae13a212d22ab5dcf40242d2';f=json.loads(FREEZE.read_bytes());sources=f.get('source_before',{})
 for name,value in sources.items():assert sha(Path(name))==value
 return {str(p):sha(p) for p in [FREEZE,ROOT/'tools/chapter09_demolition_v2/build.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts]}
START=guard();FLAG='buff/peer/live_unbalance';IMMUNE='buff/peer/unbalance_immunity';EXTRA='buff/peer/unrelated'
def scene(mode='live'):
 p=build();a={'id':'unit/peer/status_target','kind':'entity','tags':['target'],'components':{'attributes':{'base':{'max_hp':HP,'atk':0,'def':907,'mres':72,'mass_level':1}},'resources':{'hp':{'role':'health','initial':HP,'capacity':HP}},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2,'abnormal_flags':[]},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(a)
 p['rules'].append({'id':'rule/peer/inactive','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}});p['buffs'] += [{'id':FLAG,'kind':'buff','selection_flags':{'abnormal_flags':[8]}},{'id':IMMUNE,'kind':'buff','selection_flags':{'abnormal_immunes':[8]}},{'id':EXTRA,'kind':'buff','selection_flags':{'abnormal_flags':[25]}}]
 flag=next(x for x in p['buffs'] if x['id']==FLAG);immunity=next(x for x in p['buffs'] if x['id']==IMMUNE)
 schedule=[{'at':12,'effect':{'op':'apply_buff','target':2,'buff':EXTRA}},{'at':20,'effect':{'op':'apply_buff','target':2,'buff':FLAG}}]
 if mode=='remove':schedule.append({'at':43,'effect':{'op':'remove_buff','target':2,'buff':FLAG}})
 if mode=='expire':flag['duration_seconds']=.5
 if mode=='inactive':flag['active_rule']='rule/peer/inactive'
 if mode=='base_immune':a['components']['selection_state']['abnormal_immunes']=[8]
 if mode in ['buff_immune','inactive_immune']:
  schedule.append({'at':21,'effect':{'op':'apply_buff','target':2,'buff':IMMUNE}})
  if mode=='inactive_immune':immunity['active_rule']='rule/peer/inactive'
 p['scenarioDraft']={'id':'scene/peer/demolition_status/'+mode,'ruleset':'ruleset/ark_standard','cards':[BODY],'parameters':{'deploy_capacity':0},'map':{'rows':9,'cols':10},'resources':{'dp':{'initial':41,'capacity':99},'life':{'initial':99999,'capacity':99999},STOCK:{'initial':2,'capacity':2}},'initialEntities':[{'definition':a['id'],'instanceAlias':'target','position':{'row':2,'col':3}}],'commands':[{'at':9,'action':'deploy','definition':BODY,'alias':'device','position':{'row':2,'col':2},'facing':'right'}],'scheduledEffects':schedule};return bind_status_definitions(p)
