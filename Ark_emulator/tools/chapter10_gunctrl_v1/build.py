"""Source-owned Londinium cannon, explicit mixed-version/reference policy."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,math
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter10_source_prepare/predefines.native.v3.json'
RANGE=ROOT.parent/'unpack_work/campaign_tables/range_table.reference_56a.json'
P='ch10/gunctrl/';BODY='unit/'+P+'body';SHOT='ability/'+P+'shot';MARK='buff/'+P+'mark';AURA='buff/'+P+'unique';PROJECTILE='projectile/'+P+'shot'
def highest_block(inputs,params,context):
 actor=inputs['candidate'];now=context['time'];defs=params['status_definitions'];active=[]
 for b in actor['components'].get('buffs',{}).get('instances',[]):
  if b['definition'] not in defs:raise ValueError('gunctrl status dependency missing: '+b['definition'])
  if b.get('expires_at') is not None and now>=b['expires_at']:continue
  if not b.get('applicability',{}).get('control',True):continue
  active.append(defs[b['definition']])
 if any(x.get('control',{}).get('block') is False for x in active):return 0
 a=actor['components'].get('attributes',{});value=context.calculate('attributes.effective',{'base':a.get('base',{}).get('block_count',0),'modifier_layers':[m for m in a.get('modifiers',[]) if m['attribute']=='block_count'],'order':[{'layer':x} for x in a.get('layers',['flat','direct_ratio','final_ratio'])]}).value
 return -max(0,value)
def members(inputs,params,context):
 from ark_sim.domains.spatial import project_cell
 center=project_cell(inputs['center_position']);offsets={tuple(x) for x in params['offsets']};states=context['area_selection_states']['candidates'];answer=[]
 for actor in inputs['candidates']:
  t=states[str(actor['id'])];pos=project_cell(actor['components']['spatial']['position'])
  if (pos[0]-center[0],pos[1]-center[1]) not in offsets or t['side'] not in (0,1) or not t['category']&1 or not t['motion']&3:continue
  if t['camouflage'] or t.get('invisible',False):continue
  answer.append(actor['id'])
 return answer
def instant(inputs,params,context):
 return {'position':dict(inputs['positions'][0]['last_target']),'reached':True,'motion_state':{}}
def visual_plan(inputs,params,context):
 source=inputs['source'];wanted='buff/'+P+('effect_2' if source['components']['resources']['sp']['current']>0 else 'effect_1');present={b['definition'] for b in inputs['instances'] if b['source']==source['id']};ops=[]
 for b in inputs['instances']:
  if b['source']==source['id'] and b['definition'] in inputs['allowed'] and b['definition']!=wanted:ops.append({'kind':'remove','buff':b['definition'],'instance':b['id'],'generation':b['generation']})
 if wanted not in present:ops.append({'kind':'apply','buff':wanted,'duration_seconds':None})
 return {'accepted':True,'operations':ops}
def providers():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 from ark_sim.domains.selection import eligibility_profile
 return {**BUILTIN_PROVIDERS,'source.ch10.gunctrl.block':{'callable':highest_block,'version':'postfilter42-live-block-control-v1'},'source.ch10.gunctrl.members':{'callable':members,'version':'x2-21cell-live-absolute-sides-v1'},'source.ch10.gunctrl.instant':{'callable':instant,'version':'attach-immediate-retained-inputpos-frame-reference-v1'},'source.ch10.gunctrl.eligibility':{'callable':eligibility_profile,'version':'native-masks-relative-side-v1'},'source.ch10.gunctrl.visual':{'callable':visual_plan,'version':'native-idempotent-derived-owned-handles-v1'}}
def bind_status_definitions(package):
 rows=package.get('definitions',package.get('buffs',[]));defs={x['id']:{'control':deepcopy(x.get('control',{}))} for x in rows if x.get('kind')=='buff'}
 rules=package.get('rules',[]) or [x for x in rows if x.get('kind')=='rule']
 next(x for x in rules if x['id']=='rule/'+P+'score')['parameters']['status_definitions']=defs
 return package
def build(stage='level_main_10-14',*,manfred_sp_binding=None,require_complete=False):
 from ark_sim.domains.selection import DEFAULT_STATE
 data=json.loads(SOURCE.read_bytes());row=data['stages'][stage]['instances'][0];raw=row['raw_native'];attrs=row['raw_character']['phases'][0]['attributesKeyFrames'][0]['data'];skill=row['skill_selection']['level'];components=data['prefabs']['trap_058_gunctrl']['components'];attack=next(c['raw'] for c in data['skill_prefabs']['sktok_gunctrl']['components'].values() if c['native_class']=='RangedAttack');cfg=deepcopy(next(c['raw'] for c in data['skill_prefabs']['sktok_gunctrl']['components'].values() if c['native_class']=='AdvancedSelector'));cfg={k:v for k,v in cfg.items() if k.startswith('_')};range_data=json.loads(RANGE.read_bytes())['x-2'];offsets=[[x['row'],x['col']] for x in range_data['grids']]
 assert attrs['atk']==3000 and skill['spData']['spCost']==120 and skill['spData']['initSp']==0 and attack['_damageType']==3 and attack['_emitToInputPosWhenTargetIsInvalid']==1
 assert cfg['_postFilter']==42 and raw['inst']['potentialRank']=={'level_main_10-14':0,'level_main_10-15':1}[stage]
 if stage=='level_main_10-15' and (require_complete or manfred_sp_binding is not None):raise ValueError('required source-owned Manfred Funnel charge SP binding not supplied')
 p={'schemaVersion':2,'manifest':{'id':'package/'+P+stage,'metadata':{'source_locks':{str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [SOURCE,RANGE,Path(__file__)]},'native_predefine':raw,'native_skill':skill,'native_attributes':attrs,'native_range':range_data,'native_projectile':data['projectiles']['projectile_gunctrl'],'native_alert':data['bson_templates']['templates']['gunctrl_alert'],'source_version_policy':data['source_version_policy'],'reference_policy':{'ranking':'FilterType42 BLOCK_COUNT_DES; current effective block_count plus actually applicable NoBlock control; ties stable actual actor id, method-body tie policy unverified','mark':'Single persistent gunctrl per native stage; one-target aura reconciles actual live eligibility/rank each kernel tick','projectile':'Native AttachToTarget immediatelyReach1 retained position; generic projectile impacts next kernel tick, explicit replaceable frame reference; not native client timing proof','area':'Native ConstBoxRange x-2 exact21 table offsets, live cell projection at impact; absolute ALLY0/ENEMY1 masks from native side3','SP':'Fixed56 passive1/sec/init0/cap120/actual120 payment; no invented extra Manfred charge','visual':'Named effect1/effect2 children mirror sourceSP GT0; effect_camera GE0 lives on controller. Aura departure owns cleanup; no visual combat state'},'manfred_sp_binding':manfred_sp_binding,'required_dependency_slots':['Only stage10-17 feature: source-owned Manfred Funnel_*_charge SP endpoint; dmech charge_gunctrl is a different source owner'],'pending':[] if stage=='level_main_10-14' else ['Stage10-17 Manfred additional Funnel charge SP endpoint binding absent'],'whole_consumer_complete':stage=='level_main_10-14','client_verified':False}},'rules':[],'buffs':[],'selectors':[],'entities':[],'abilities':[],'projectiles':[]}
 def rule(name,contract,provider,params=None):return {'id':'rule/'+P+name,'kind':'rule','contract':contract,'parameters':params or {},'implementation':{'type':'provider','provider':provider}}
 p['rules']=[rule('visual','buff.application','source.ch10.gunctrl.visual'),rule('score','targeting.score','source.ch10.gunctrl.block'),rule('members','area.members','source.ch10.gunctrl.members',{'offsets':offsets}),rule('motion','projectile.trajectory','source.ch10.gunctrl.instant'),rule('collision','projectile.collision','model.projectile.collision'),rule('eligibility','targeting.eligibility','source.ch10.gunctrl.eligibility')]
 eligibility={'rule':'rule/'+P+'eligibility','parameters':{'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':DEFAULT_STATE}}
 sid='selector/'+P+'highest';p['selectors']=[{'id':sid,'kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'limit':1,'eligibility':eligibility}]
 def apply(name,condition=None):
  e={'op':'apply_buff','target':'target','buff':'buff/'+P+name}
  if condition:e['condition']=condition
  return e
 def remove(name):return {'op':'remove_buff','target':'target','buff':'buff/'+P+name}
 high='inputs.source.components.resources.sp.current > 0';low='inputs.source.components.resources.sp.current <= 0'
 visual=[{'op':'buff_application','target':'target','application_rule':'rule/'+P+'visual','allowed':['buff/'+P+'effect_1','buff/'+P+'effect_2']}]
 p['buffs']=[{'id':AURA,'kind':'buff','aura':{'selector':sid,'buff':MARK}}, {'id':MARK,'kind':'buff','stacking':{'mode':'independent'},'interval_seconds':1/30,'events':[{'event':'buff.applied','condition':"inputs.payload.target == context.owner.id and inputs.payload.buff == 'buff/ch10/gunctrl/mark'",'effects':visual}],'effects':visual,'on_remove':[remove('effect_1'),remove('effect_2')]}, {'id':'buff/'+P+'effect_1','kind':'buff','metadata':{'native_key':'gunctrl_alert[effect_1]','effect':'map_027_chengfangpao_buff_01'}},{'id':'buff/'+P+'effect_2','kind':'buff','metadata':{'native_key':'gunctrl_alert[effect_2]','effect':'map_027_chengfangpao_buff_02'}},{'id':'buff/'+P+'camera','kind':'buff','events':[{'event':'buff.applied','condition':"inputs.payload.target == context.owner.id and inputs.payload.buff == 'buff/ch10/gunctrl/camera'",'effects':[apply('effect_camera')]}], 'on_remove':[remove('effect_camera')]},{'id':'buff/'+P+'effect_camera','kind':'buff','metadata':{'native_key':'gunctrl_alert[effect_camera]'}},{'id':'buff/'+P+'native_flags','kind':'buff','selection_flags':{'abnormal_flags':[5,7]}}]
 p['projectiles']=[{'id':PROJECTILE,'kind':'projectile','motion':{'rule':'rule/'+P+'motion'},'collision':{'rule':'rule/'+P+'collision','parameters':{'enabled':False}},'lifetime_seconds':10,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':True,'completion_blocking':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}]
 blast={'op':'area','target':'target','center':'target','projectile_definition':PROJECTILE,'membership_rule':'rule/'+P+'members','selection_projection':{'defaults':DEFAULT_STATE},'effects':[{'op':'damage','damage_type':'true','scale':1}]}
 p['abilities']=[{'id':SHOT,'kind':'ability','activation':{'mode':'manual','parameters':{'auto_only':True,'auto_when_ready':True},'costs':[{'resource':'sp','amount':120}],'condition':'inputs.source.components.resources.sp.current >= 120'},'selector':sid,'target_capture':'at_cast','parameters':{'allow_no_target':True},'timeline':[{'at':0,'effect':blast}]}]
 p['entities']=[{'id':BODY,'kind':'entity','tags':['gunctrl','mechanism'],'rules':{'targeting.score':'rule/'+P+'score'},'components':{'attributes':{'base':{'max_hp':10000,'atk':3000,'def':0,'mres':0,'block_count':0}},'resources':{'hp':{'role':'health','initial':10000,'capacity':10000},'sp':{'initial':0,'capacity':120,'recovery_rate':1}},'selection_state':{'side':1,'motion':1,'category':2,'unit_type':4},'spatial':{'motion_mode':0},'buffs':{'initial':[AURA,'buff/'+P+'camera','buff/'+P+'native_flags']},'abilities':[SHOT],'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
 return bind_status_definitions(p)
