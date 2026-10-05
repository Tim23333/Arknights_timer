"""Independent source rock mode fixtures; frozen modules/providers only."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_rock_modes_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from tools.chapter09_rock_modes_v2.build import providers
CORE='ed5ad49acb134bf00b90b758d7cad0e95f4ec20125f70765ed591f90fef58af4';assert implementation_digest()==CORE
BASE=ROOT/'packages/campaign/chapter09_consumers/rock_modes_v2';FREEZE=ROOT/'validation/campaign/chapter09_rock_modes_v2/freeze.v2.json';PAYLOAD=ROOT/'packages/campaign/chapter09_consumers/pillars/collapse.payload.v1.json';REPORT=ROOT/'validation/campaign/chapter09_rock_modes_peer';LOG=Path('E:/ArkSimLogs/runs/chapter09_rock_modes_peer');REG=providers();HP=13739
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(FREEZE)=='83a9834b1bcba34eb3c19ddcf1a5263d1a4cbece9bc2e925c86cdcdb0fcddbaa';f=json.loads(FREEZE.read_bytes());assert f['core']==CORE
 for module in f['modules']:assert sha(ROOT/module['path'])==module['sha']
 paths=[FREEZE,PAYLOAD,ROOT/'tools/chapter09_rock_modes_v2/build.py',ROOT/'tools/chapter09_rock_gargoyle/build_v1.py',ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts]+list(BASE.glob('*.json'));return {str(p):sha(p) for p in paths}
START=guard()
def person(name):return {'id':'unit/peer/rock/'+name,'kind':'entity','tags':['player',name],'components':{'attributes':{'base':{'max_hp':27103,'atk':50000,'def':731,'mres':43,'block_count':2}},'resources':{'hp':{'role':'health','initial':27103,'capacity':27103}},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
def rock(kind='durokt',profile='prts_reference',block=False):
 key={'durokt':'enemy_1171_durokt','dugago':'enemy_1172_dugago'}[kind];p=json.loads((BASE/(key+'.'+profile+'.json')).read_bytes());p['manifest']['requires']=['preset/ark_standard'];trait=next(b for b in json.loads(PAYLOAD.read_bytes())['buffs'] if b['id']=='buff/ch9/pillar/trait');p['buffs'].append(trait);body=p['entities'][0];body['components']['attributes']['base'].update(max_hp=HP,atk=533,**{'def':613,'mres':17,'attack_interval':4.1,'attack_speed_ratio':1.25});body['components']['resources']['hp']['initial']=HP
 controller=person('controller');controller['components']['abilities']=['ability/peer/rock/stun','ability/peer/rock/hit','ability/peer/rock/clear_stone'];p['entities'].append(controller);p['buffs'].append({'id':'buff/peer/rock/stun','kind':'buff','duration_seconds':.2,'selection_flags':{'abnormal_flags':[0]},'control':{'move':False,'attack':False,'abilities':False,'interrupt':True}});p['selectors'].append({'id':'selector/peer/rock/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'] += [{'id':'ability/peer/rock/stun','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/rock/enemy','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/peer/rock/stun'}}]},{'id':'ability/peer/rock/hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/rock/enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]},{'id':'ability/peer/rock/clear_stone','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/rock/enemy','timeline':[{'at':0,'effect':{'op':'remove_buff','buff':'buff/ch9/dugago/stone'}}]}]
 if kind=='durokt':
  controller['components']['abilities'].remove('ability/peer/rock/clear_stone');p['abilities']=[a for a in p['abilities'] if a['id']!='ability/peer/rock/clear_stone']
 initial=[{'definition':body['id'],'instanceAlias':'enemy','position':{'row':2,'col':2},'route':{'motionMode':'WALK','startPosition':{'row':2,'col':2},'endPosition':{'row':2,'col':10},'checkpoints':[]}},{'definition':controller['id'],'instanceAlias':'controller','position':{'row':9,'col':9}}]
 if block:
  b=person('blocker');b['components']['deployable']={'base_cost':0,'terrain':'ground','capacity':1,'cooldown_seconds':0};b['components']['abilities']=['ability/peer/rock/leave'];p['entities'].append(b);p['abilities'].append({'id':'ability/peer/rock/leave','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':{'row':8,'col':8}}}]});initial.append({'definition':b['id'],'instanceAlias':'blocker','position':{'row':2,'col':2},'deployed':True})
 p['scenarioDraft']={'id':'scene/peer/rock/'+kind+'/'+profile,'ruleset':'ruleset/ark_standard','map':{'rows':11,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial,'commands':[]};return p

def hover(independent=True,land=None):
 h={'id':'unit/peer/hover','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':8579,'atk':0,'def':337,'mres':61,'move_speed':1.7,'mass_level':4,'block_cost':1}},'resources':{'hp':{'role':'health','initial':8579,'capacity':8579}},'spatial':{'motion_mode':1},'selection_state':{'side':1,'motion':2,'category':1,'unit_type':2},'abilities':['ability/peer/hover/land']}}
 if independent:h['components']['spatial']['route_motion_mode']=0
 b=person('hover_blocker');b['components']['deployable']={'base_cost':0,'terrain':'ground','capacity':1,'cooldown_seconds':0};tiles=[{'tileKey':'tile_floor','buildableType':1,'passableMask':3} for _ in range(45)]
 for col in [3,4]:tiles[18+col]={'tileKey':'tile_wall','buildableType':0,'passableMask':2}
 p={'schemaVersion':2,'manifest':{'id':'package/peer/hover','requires':['preset/ark_standard']},'entities':[h,b],'abilities':[{'id':'ability/peer/hover/land','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'set_motion_mode','target':'source','value':0,'parameters':{'route_motion_mode':0}}}]}],'scenarioDraft':{'id':'scene/peer/hover','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':9,'tiles':tiles},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':h['id'],'instanceAlias':'hover','position':{'row':2,'col':1},'route':{'motionMode':0,'startPosition':{'row':2,'col':1},'endPosition':{'row':2,'col':7},'checkpoints':[]}},{'definition':b['id'],'instanceAlias':'blocker','position':{'row':2,'col':1},'deployed':True}],'commands':[]}}
 if land is not None:p['scenarioDraft']['commands']=[{'at':land,'action':'skill','source':'hover','ability':'ability/peer/hover/land'}]
 return p
