"""Independent owned-clock/Flame fixtures, no author test-fixture imports."""
import sys,json,hashlib,math
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_pillar_channel_joint_v3_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
CORE='4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4';FLAME=ROOT/'packages/campaign/chapter09_consumers/linked_elemental/flame.channel.v1.json';HELPER=ROOT/'tools/chapter09_ability_clock_v1/flame_channel.py';SOURCE=ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json';REPORT=ROOT/'validation/campaign/chapter09_clock_peer_pillar_joint_v3';LOG=Path('E:/ArkSimLogs/runs/chapter09_clock_peer_pillar_joint_v3')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE
 return {str(p):sha(p) for p in [FLAME,HELPER,SOURCE]+[x for x in (CAND/'ark_sim').rglob('*') if x.is_file() and x.suffix in ('.py','.json')]}
START=guard()
def custom_recovery(i,p,c):
 if not c.get('source',{}):raise ValueError('peer recovery requires actual source scope')
 if c.get('target',{}) and c.get('owner',{}).get('id')!=c['target']['id']:raise ValueError('peer recovery requires actual owned target scope')
 return i['recovery_parameters']['seconds'] * 1.5

def homing(i,p,c):
 q=i['positions'][0];a=q['position'];b=q['last_target'];dr=b['row']-a['row'];dc=b['col']-a['col'];distance=math.hypot(dr,dc);step=i['trajectory_parameters']['speed']*i['trajectory_parameters']['delta_seconds'];hit=distance<=step+1e-12;scale=1 if hit else step/distance
 return {'position':{'row':a['row']+scale*dr,'col':a['col']+scale*dc},'reached':hit,'motion_state':{}}
REG={**BUILTIN_PROVIDERS,'peer.clock.recovery':{'callable':custom_recovery,'version':'independent-1'},'model.linked.homing':{'callable':homing,'version':'independent-homing-1'}}

def actor(name):return {'id':'unit/peer/'+name,'kind':'entity','tags':[name],'components':{'attributes':{'base':{'max_hp':31007,'atk':321,'def':127,'mres':37}},'resources':{'hp':{'role':'health','initial':31007,'capacity':31007}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
def clock_scene(effect_override=False,cycle=False):
 worker=actor('worker');director=actor('director');worker['components']['abilities']=['ability/peer/work'];director['components']['abilities']=['ability/peer/set_clock','ability/peer/stop_work']
 work={'id':'ability/peer/work','kind':'ability','activation':{'mode':'manual'},'duration_seconds':2,'rules':{'ability.recovery':'rule/peer/own_recovery'},'timeline':[{'at_seconds':1,'effect':{'op':'emit','event':'peer.work.hit'}}]}
 effect={'op':'set_ability_cooldown','ability':work['id'],'duration_seconds':1.25}
 if effect_override:effect['rules']={'ability.recovery':'rule/peer/effect_recovery'}
 setclock={'id':'ability/peer/set_clock','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/worker','rules':{'ability.recovery':'rule/peer/caller_recovery'},'timeline':[{'at':0,'effect':effect}]};stop={'id':'ability/peer/stop_work','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/worker','timeline':[{'at':0,'effect':{'op':'interrupt_ability','ability':work['id']}}]}
 p={'schemaVersion':2,'manifest':{'id':'package/peer/ownedclock','requires':['preset/ark_standard']},'entities':[worker,director],'selectors':[{'id':'selector/peer/worker','kind':'selector','region':{'type':'all'},'filters':[{'tag':'worker'}],'limit':1}],'rules':[{'id':'rule/peer/own_recovery','kind':'rule','contract':'ability.recovery','implementation':{'type':'provider','provider':'peer.clock.recovery'}},{'id':'rule/peer/effect_recovery','kind':'rule','contract':'ability.recovery','implementation':{'type':'expression','expression':'inputs.recovery_parameters.seconds * 2'}},{'id':'rule/peer/caller_recovery','kind':'rule','contract':'ability.recovery','implementation':{'type':'expression','expression':'inputs.recovery_parameters.seconds * 9'}}],'abilities':[work,setclock,stop],'scenarioDraft':{'id':'scene/peer/ownedclock','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':4},'initialEntities':[{'definition':worker['id'],'instanceAlias':'worker','position':{'row':1,'col':2}},{'definition':director['id'],'instanceAlias':'director','position':{'row':0,'col':0}}],'commands':[{'at':7,'action':'skill','source':'director','ability':setclock['id']}]}}
 if cycle:
  work['activation']['on_start']=[{'op':'apply_buff','target':'source','buff':'buff/peer/cycle'}];p['buffs']=[{'id':'buff/peer/cycle','kind':'buff','on_remove':[{'op':'interrupt_ability','ability':work['id']},{'op':'set_ability_cooldown','ability':work['id'],'duration_seconds':1.25}]}]
 return p

def flame_scene(stun_at=None,kill_at=None,hp=31007):
 p=json.loads(FLAME.read_bytes());p['manifest']['requires']=['preset/ark_standard'];source=p['entities'][0];target=p['entities'][1];source['components']['attributes']['base']['atk']=800;target['components']['attributes']['base'].update(max_hp=hp,mres=35);target['components']['resources']['hp'].update(initial=hp,capacity=hp)
 director=actor('director');director['components']['attributes']['base']['atk']=100000;director['components']['abilities']=['ability/peer/stun_source','ability/peer/kill_target'];p['entities'].append(director)
 p['selectors'] += [{'id':'selector/peer/flame_source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1}]
 p['buffs'].append({'id':'buff/peer/stun','kind':'buff','duration_seconds':2,'selection_flags':{'abnormal_flags':[0]},'control':{'abilities':False,'attack':False,'move':False,'interrupt':True}})
 p['abilities'] += [{'id':'ability/peer/stun_source','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/flame_source','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/peer/stun'}}]},{'id':'ability/peer/kill_target','kind':'ability','activation':{'mode':'manual'},'selector':'selector/linked/target','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}]
 p['scenarioDraft']={'id':'scene/peer/flameclock','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':6},'initialEntities':[{'definition':source['id'],'instanceAlias':'flame','position':{'row':1,'col':1}},{'definition':target['id'],'instanceAlias':'victim','position':{'row':1,'col':3}},{'definition':director['id'],'instanceAlias':'director','position':{'row':0,'col':5}}],'commands':[]}
 if stun_at is not None:p['scenarioDraft']['commands'].append({'at':stun_at,'action':'skill','source':'director','ability':'ability/peer/stun_source'})
 if kill_at is not None:p['scenarioDraft']['commands'].append({'at':kill_at,'action':'skill','source':'director','ability':'ability/peer/kill_target'})
 return p
