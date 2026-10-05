"""Independent bounded actual zero-health protocol peer; no author fixture imports."""
import sys,json,hashlib,math
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_pillar_channel_joint_v3_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
CORE='4d42e2b6cf646ebe2291d695f82d968e5d4669217069a37bcc8b2babb850f7a4';FREEZE=ROOT/'validation/campaign/chapter09_depletion_peer_joint_v3/identity.freeze.json';REPORT=ROOT/'validation/campaign/chapter09_depletion_peer_joint_v3';LOG=Path('E:/ArkSimLogs/runs/chapter09_depletion_peer_joint_v3')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE
 freeze=json.loads(FREEZE.read_bytes());assert freeze['core_before']==freeze['core_after']==CORE
 for d in freeze['delta']:assert sha(CAND/d['path'])==d['candidate_sha256']
 return {str(p):sha(p) for p in [FREEZE]+[x for x in (CAND/'ark_sim').rglob('*') if x.is_file() and x.suffix in ('.py','.json')]}
START=guard()
def plan(i,p,c):
 if c['time']!=i['clock']['time'] or c['owner']['id']!=i['target']['id'] or c['target']['id']!=i['target']['id']:raise ValueError('peer original plan context mismatch')
 r=i['request']
 if r['operation']=='damage' and r['health_before']>0 and r['health_after']==0 and i['state']['generation']==0:return {'action':'defer','stage':'zero','actions':['mark','ready']}
 if i['state']['generation']>0:return {'action':'none','stage':i['state']['stage'],'actions':[]}
 return {'action':'finish','stage':i['state']['stage'],'actions':[]}
def death(i,p,c):return {'action':'death' if i['resources']['vital']['current']<=0 else 'none'}
def quantize(i,p,c):
 owned=c.get('depletion_schedule_next_seq') is not None
 if owned and c.get('depletion_effect_phase') is None:raise ValueError('peer quantize lacks original owned clock context')
 return math.ceil(i['seconds']/i['quantum']*(1.5 if owned else 1)-1e-9)
REG={**BUILTIN_PROVIDERS,'peer.depletion.plan':{'callable':plan,'version':'independent-plan-context-1'},'peer.depletion.death':{'callable':death,'version':'independent-vital49-1'},'peer.depletion.time':{'callable':quantize,'version':'independent-time1point5-1'}}

def fixture(custom_clock=False,fault=False):
 stages={'initial':{'active':True,'selectable':True},'zero':{'active':False,'selectable':False},'marked':{'active':False,'selectable':False},'ready':{'active':True,'selectable':False}}
 actions={'mark':{'at_seconds':.2,'next_stage':'marked','effects':[{'op':'emit','event':'peer.zero.mark'}]},'ready':{'at_seconds':2.25,'next_stage':'ready','effects':[{'op':'emit','event':'peer.zero.ready'}]}}
 if fault:actions['mark']['effects']=[{'op':'random','stream':'peer/depletion_error','probability':1,'on_success':[{'op':'emit','event':'peer.pre_error'}]},{'op':'modify_resource','resource':'vital','value':1}]
 owner={'id':'unit/peer/owner','kind':'entity','tags':['owner'],'components':{'attributes':{'base':{'max_hp':49,'atk':121,'def':11,'mres':0}},'resources':{'vital':{'role':'health','initial':49,'capacity':49}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle','rules':{'lifecycle.death':'rule/peer/vital_death'}},'depletion':{'resource':'vital','rule':'rule/peer/plan_outer','initial_stage':'initial','stages':stages,'actions':actions,'parameters':{}},'abilities':[]}}
 source={'id':'unit/peer/caster','kind':'entity','tags':['caster'],'components':{'attributes':{'base':{'max_hp':913,'atk':293,'def':17,'mres':19}},'resources':{'hp':{'role':'health','initial':913,'capacity':913}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/lethal','ability/peer/raw_zero','ability/peer/retire_owner']}}
 fields={'source':'inputs.source','target':'inputs.target','request':'inputs.request','state':'inputs.state','clock':'inputs.clock','parameters':'inputs.parameters'}
 rules=[{'id':'rule/peer/plan_leaf','kind':'rule','contract':'resource.depletion','implementation':{'type':'provider','provider':'peer.depletion.plan'}},{'id':'rule/peer/plan_nested','kind':'rule','contract':'resource.depletion','implementation':{'type':'graph','nodes':[{'id':'inner','rule':'rule/peer/plan_leaf','inputs':fields}],'output':'nodes.inner'}},{'id':'rule/peer/plan_outer','kind':'rule','contract':'resource.depletion','implementation':{'type':'graph','nodes':[{'id':'outer','rule':'rule/peer/plan_nested','inputs':fields}],'output':'nodes.outer'}},{'id':'rule/peer/vital_death','kind':'rule','contract':'lifecycle.death','implementation':{'type':'provider','provider':'peer.depletion.death'}}]
 p={'schemaVersion':2,'manifest':{'id':'package/peer/depletion49','requires':['preset/ark_standard']},'entities':[owner,source],'rules':rules,'selectors':[{'id':'selector/peer/owner','kind':'selector','region':{'type':'all'},'filters':[{'tag':'owner'}],'limit':1}],'abilities':[],'scenarioDraft':{'id':'scene/peer/depletion49','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'initialEntities':[{'definition':owner['id'],'instanceAlias':'owner','position':{'row':2,'col':3}},{'definition':source['id'],'instanceAlias':'caster','position':{'row':0,'col':1}}],'commands':[{'at':11,'action':'skill','source':'caster','ability':'ability/peer/lethal'}]}}
 for name,effect in [('lethal',{'op':'damage','damage_type':'true','scale':1,'resource':'vital'}),('raw_zero',{'op':'modify_resource','resource':'vital','value':0,'parameters':{'operation':'damage','source':'caster'}}),('retire_owner',{'op':'retire','parameters':{'reason':'withdrawn'}})]:p['abilities'].append({'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/owner','timeline':[{'at':0,'effect':effect}]})
 if custom_clock:
  p['rules'].append({'id':'rule/peer/time','kind':'rule','contract':'time.quantize','implementation':{'type':'graph','nodes':[{'id':'clock','rule':'rule/peer/time_leaf','inputs':{'seconds':'inputs.seconds','quantum':'inputs.quantum','rounding':'inputs.rounding'}}],'output':'nodes.clock'}});p['rules'].append({'id':'rule/peer/time_leaf','kind':'rule','contract':'time.quantize','implementation':{'type':'provider','provider':'peer.depletion.time'}});p['scenarioDraft']['rules']={'time.quantize':'rule/peer/time'}
 return p
