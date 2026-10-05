"""Independent receiving records, holder writes and source marker fixtures."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_c9_receiver_hooks_v2_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw,digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from tools.chapter09_receiver_hooks_v1.build import providers as source_providers,MARK
CORE='77049fb9724675de47f4fb8bb72e5696b64f4737156acf513f1b7963015d9050';assert implementation_digest()==CORE
FREEZE=ROOT/'validation/campaign/chapter09_receiver_hooks_v2/freeze.v2.json';BASE=ROOT/'packages/campaign/chapter09_consumers/receiver_hooks_v2';PAYLOAD=ROOT/'packages/campaign/chapter09_consumers/pillars/collapse.payload.v1.json';REPORT=ROOT/'validation/campaign/chapter09_receiver_hooks_peer';LOG=Path('E:/ArkSimLogs/runs/chapter09_receiver_hooks_peer');HP=16381;TRAIT='buff/ch9/pillar/trait';SIGNAL='buff/peer/receiver_signal';HOLDER='buff/peer/receiver_holder'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 assert implementation_digest()==CORE;assert sha(FREEZE)=='0b7b3239a30e056ca09055e114f1636829cc9fe1a6d7254a6af4f0d8c2060176';f=json.loads(FREEZE.read_bytes());assert f['core']==CORE
 for x in f['delta']:assert sha(CAND/x['path'])==x['after']
 for x in f['modules']:assert sha(ROOT/x['path'])==x['sha']
 paths=[FREEZE,PAYLOAD,ROOT/'tools/chapter09_receiver_hooks_v1/build.py',ROOT/'tools/chapter09_rock_modes_v2/build.py',ROOT/'tools/chapter09_rock_gargoyle/build_v1.py',ROOT/'packages/campaign/chapter09_source_prepare/enemies.native.v1.json']+list(BASE.glob('*.json'))+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json'] and 'validation' not in p.parts];return {str(p):sha(p) for p in paths}
START=guard()
def request(i,p,c):
 assert c['owner']['id']==c['target']['id']==i['target']['id'];assert c['source']['id']==i['source']['id'];assert c['source']['components']['attributes']['base']['atk']==619;assert c['time']==i['effect']['parameters']['expected_tick']
 if p.get('hostwrite'):c['source']['components']['attributes']['base']['atk']=0
 effect=dict(i['effect']);effects=[{'op':'emit','event':'peer.receiver.pre','payload':{'actual_source':i['source']['id'],'holder':i['target']['id']}},{'op':'apply_buff','buff':SIGNAL}]
 if p.get('foreign'):effects[0]['target']=4
 if p.get('foreignop'):effects=[{'op':'damage','damage_type':'true','scale':1}]
 if p.get('overflow'):effects=[{'op':'emit','event':'peer.overflow'}]*33
 if p.get('badbool'):return {'accepted':1,'effect':effect,'effects':[]}
 return {'accepted':not p.get('deny',False),'effect':effect,'effects':effects}
REG={**source_providers(),'peer.receiver.request':{'callable':request,'version':'independent-actual-source-holder-freeze-v2'}}
def person(name,hp,atk):return {'id':'unit/peer/receiver/'+name,'kind':'entity','tags':[name],'components':{'attributes':{'base':{'max_hp':hp,'atk':atk,'def':417,'mres':63}},'resources':{'hp':{'role':'health','initial':hp,'capacity':hp}},'selection_state':{'side':0 if name!='target' else 1,'motion':1,'category':1,'unit_type':1 if name!='target' else 2},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[]}}
def protocol(**options):
 source=person('source',33317,619);source['components']['abilities']=['ability/peer/receiver_hit'];target=person('target',9933,0);target['components']['buffs']={'initial':[HOLDER]};foreign=person('foreign',27307,0)
 p={'schemaVersion':2,'manifest':{'id':'package/peer/receiver_protocol','requires':['preset/ark_standard']},'entities':[source,target,foreign],'selectors':[{'id':'selector/peer/receiver','kind':'selector','region':{'type':'all'},'filters':[{'tag':'target'}],'limit':1}],'abilities':[{'id':'ability/peer/receiver_hit','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/receiver','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1,'parameters':{'expected_tick':17}}}]}],'buffs':[{'id':SIGNAL,'kind':'buff','duration_seconds':1},{'id':HOLDER,'kind':'buff','damage_hooks':[{'phase':'receiver_request','rule':'rule/peer/receiver','after_effects':[{'op':'remove_buff','buff':SIGNAL},{'op':'emit','event':'peer.receiver.post'}]}]}],'rules':[{'id':'rule/peer/receiver','kind':'rule','contract':'damage.request','dependencies':[SIGNAL],'parameters':options,'implementation':{'type':'provider','provider':'peer.receiver.request'}}],'scenarioDraft':{'id':'scene/peer/receiver_protocol','ruleset':'ruleset/ark_standard','map':{'rows':4,'cols':8},'initialEntities':[{'definition':source['id'],'instanceAlias':'source','position':{'row':2,'col':0}},{'definition':target['id'],'instanceAlias':'target','position':{'row':2,'col':4}},{'definition':foreign['id'],'instanceAlias':'foreign','position':{'row':3,'col':6}}],'commands':[{'at':17,'action':'skill','source':'source','ability':'ability/peer/receiver_hit'}]}}
 return p

def gargoyle(profile='native_literal',source_mode='active',damage=677,ordinary_tick=16):
 p=json.loads((BASE/('dugago.'+profile+'.json')).read_bytes());p['manifest']['requires']=['preset/ark_standard'];trait=next(x for x in json.loads(PAYLOAD.read_bytes())['buffs'] if x['id']==TRAIT);trait=deepcopy(trait);p['buffs'].append(trait);body=p['entities'][0];body['components']['attributes']['base'].update(max_hp=HP,atk=521,**{'def':947,'mres':29});body['components']['resources']['hp']['initial']=HP
 if source_mode=='inactive':trait['active_rule']='rule/peer/inactive'
 if source_mode=='expiry':trait['duration_seconds']=13/30
 if source_mode in ['inactive','holder_inactive']:p['rules'].append({'id':'rule/peer/inactive','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}})
 if source_mode=='holder_inactive':next(x for x in p['buffs'] if x['id']=='buff/ch9/dugago/pillar_check')['active_rule']='rule/peer/inactive'
 pillar=person('pillar_actor',33317,damage);pillar['components']['abilities']=['ability/peer/pillar_hit'];pillar['components']['buffs']={'initial':[] if source_mode=='absent' else [TRAIT]};ordinary=person('ordinary',33317,23000);ordinary['components']['abilities']=['ability/peer/ordinary_burst'];p['entities'] += [pillar,ordinary];p['selectors'].append({'id':'selector/peer/gargoyle','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
 for aid in ['ability/peer/pillar_hit','ability/peer/ordinary_burst']:p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/gargoyle','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]})
 p['scenarioDraft']={'id':'scene/peer/receiver_gargoyle/'+profile+'/'+source_mode,'ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':10},'initialEntities':[{'definition':body['id'],'instanceAlias':'enemy','position':{'row':3,'col':3}},{'definition':pillar['id'],'instanceAlias':'pillar_actor','position':{'row':7,'col':7}},{'definition':ordinary['id'],'instanceAlias':'ordinary','position':{'row':8,'col':7}}],'commands':[{'at':13,'action':'skill','source':'pillar_actor','ability':'ability/peer/pillar_hit'}]}
 if ordinary_tick is not None:p['scenarioDraft']['commands'].append({'at':ordinary_tick,'action':'skill','source':'ordinary','ability':'ability/peer/ordinary_burst'})
 return p
