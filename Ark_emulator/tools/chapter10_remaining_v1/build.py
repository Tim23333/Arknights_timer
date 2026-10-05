"""Native global aura and source-frame attacks; absent chain is rejected."""
from pathlib import Path
from copy import deepcopy
import json,hashlib
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'packages/campaign/chapter10_consumers/remaining/source.closure.v1.json'
PREFIX='ch10/remaining/';MARK='buff/ch10/bloodline/bloodsucker_mark';SUPPLY='buff/'+PREFIX+'supply_child'

def eligible(inputs,params,context):
 from ark_sim.domains.selection import eligibility_profile
 answer=eligibility_profile(inputs,params,context)
 if not answer['accepted']:return answer
 if params.get('bloodsucker_required'):
  when=context['time'];buffs=inputs['candidate']['components'].get('buffs',{}).get('instances',[])
  if not any(x['definition']==params['bloodsucker_mark'] and (x.get('expires_at') is None or when<x['expires_at']) and x.get('applicability',{}).get('active',True) for x in buffs):return {'accepted':False,'reason':'missing_actual_source_bloodsucker_mark'}
 return answer

def counter(actor,now,definition):
 return [b for b in actor['components'].get('buffs',{}).get('instances',[]) if b['definition']==definition and (b.get('expires_at') is None or now<b['expires_at']) and b.get('applicability',{}).get('active',True)]

def attack_value(inputs,params,context):
 actor=context['owner'];mods=deepcopy(list(inputs['modifier_layers']));extra=0
 children=counter(actor,context['time'],SUPPLY);child_ids={x['id'] for x in children};mods=[x for x in mods if x.get('buff_instance') not in child_ids]
 if children:extra+=.1*min(5,len(children))
 for b in counter(actor,context['time'],'buff/'+PREFIX+'lord_parent'):
  extra+=.25*min(6,len(b.get('aura_members',{})))
 if extra:mods.append({'attribute':'atk','layer':'direct_ratio','value':extra,'stacks':1})
 return context.calculate('attributes.effective',{'base':inputs['base'],'modifier_layers':mods,'order':inputs['order']},rule_id=params['base_rule']).value

def supply_damage(inputs,params,context):
 from ark_sim.contracts import thaw
 effect=thaw(inputs['effect']);source=inputs['source'];n=min(5,len(counter(source,context['time'],SUPPLY)));amount=effect.get('attack',source['components']['attributes']['base']['atk'])*.1*n
 return {'accepted':True,'effect':effect,'effects':[{'op':'elemental_damage','target':'target','element':'DARK','amount':amount}] if n else []}

def providers():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 from ark_sim.domains.projectile_profiles import trajectory
 return {**BUILTIN_PROVIDERS,'source.ch10.remaining.eligible':{'callable':eligible,'version':'actual-bloodsucker-source-ground-global-v1'},'source.ch10.remaining.atk':{'callable':attack_value,'version':'source-reverse-lord6-supply5-native-additive-v1'},'source.ch10.remaining.ep':{'callable':supply_damage,'version':'actual-source-currentATK-dark-stack5-v1'},'source.ch10.remaining.motion':{'callable':trajectory,'version':'native-speed10-planar-reference-v1'}}

def bind_recipients(p):
 rows=p.get('definitions',p.get('entities',[]));rules=p.get('rules',[]) or [d for d in rows if d.get('kind')=='rule']
 for d in rows:
  if d.get('kind')!='entity' or 'atk' not in d.get('components',{}).get('attributes',{}).get('base',{}):continue
  attrs=d['components']['attributes'];existing=attrs.get('attribute_rules',{}).get('atk',{}).get('attributes.effective','rule/ark_attribute_layers')
  if existing.startswith('rule/'+PREFIX+'atk/'):continue
  rid='rule/'+PREFIX+'atk/'+d['id'].replace('/','_');rules.append({'id':rid,'kind':'rule','contract':'attributes.effective','dependencies':[existing],'parameters':{'base_rule':existing},'implementation':{'type':'provider','provider':'source.ch10.remaining.atk'}});attrs.setdefault('attribute_rules',{})['atk']={'attributes.effective':rid}
 return p

def build(key,*,bloodsucker_mark=None,deathrattle=None,require_complete=False):
 from ark_sim.domains.selection import DEFAULT_STATE
 data=json.loads(SOURCE.read_bytes())
 if key not in data['variants']:raise ValueError('unsupported exact source variant')
 if key=='enemy_1225_dkmage_2':raise ValueError('native ChainLightningHitBehaviour requires actual chained impact primitive; no empty or parallel target fallback')
 if bloodsucker_mark is None or bloodsucker_mark.get('id')!=MARK or bloodsucker_mark.get('kind')!='buff':raise ValueError('actual source bloodsucker mark Buff dependency required')
 if require_complete and key=='enemy_1226_dklord_2' and deathrattle is None:raise ValueError('actual bloodline deathrattle consumer required')
 if deathrattle is not None:raise ValueError('supplied deathrattle bridge pending exact frozen module merge; no metadata-only grant')
 v=data['variants'][key];native=v['native_enemy']['resolved'];a=native['attributes'];is_lord=key=='enemy_1226_dklord_2';nodes=v['modes'][0]['nodes'];attack=nodes['_combat' if is_lord else '_attack'];binding=attack['animation_binding'];prefab=data['prefabs'][key]
 validator=next(x['raw'] for x in prefab['components'].values() if x.get('native_class')=='FilterBuffTargetValidator');o=validator['_targetOptions'];assert validator['_buffs']==['enemy_bloodsucker_mark'] and o['targetSide']==1 and o['targetMotion']==1
 configs=[]
 for entry in prefab['components'].values():
  if entry.get('native_class')=='AdvancedSelector':configs.append({k:z for k,z in entry['raw'].items() if k.startswith('_')})
 cfg=configs[0] if configs else None
 aura_cfg={'_targetSide':o['targetSide'],'_targetMotion':o['targetMotion'],'_targetCategory':o['targetCategory'],'_ignoreTargetFree':o['ignoreTargetFree'],'_onlyIgnoreSomeOfTargetFreeCase':o['onlyIgnoreSomeOfTargetFreeCase'],'_abnormalFlag':o['abnormalFlag'],'_abnormalCombo':o['abnormalCombo'],'_ignoreAllyTargetFree':o['ignoreAllyTargetFree'],'_ignoreHealFree':o['ignoreHealFree'],'_ignoreMotionMode':o['ignoreMotionMode'],'_forceIgnoreCamouflage':0,'_needProfessionMask':0,'_professionMask':o['professionMask'],'_excludeSomeAbnormalFlags':o['excludeSomeAbnormalFlags'],'_excludeAbnormalFlag':o['excludeAbnormalFlag'],'_checkUnitType':o['checkUnitType'],'_unitTypeMask':o['unitTypeMask']}
 local='lord' if is_lord else 'supply';body='unit/'+PREFIX+local;normal='ability/'+PREFIX+local+'_normal';parent='buff/'+PREFIX+local+'_parent';child='buff/'+PREFIX+local+'_child'
 p={'schemaVersion':2,'manifest':{'id':'package/'+PREFIX+key,'metadata':{'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'native_variant':v,'source_prefab':prefab,'source_policy':{'mode':'Only real source mode0; dklord has _attack=null and real melee _combat; no fabricated ranged mode','animation':'Exact source authored frame normalization, kept original float32 records','aura':'Source global range only live allied ground/category1 with actual supplied bloodsucker Buff; dklord sourceATK+.25/member cap6; supply targetATK+.1 cap5 and DARKEP .1/current ATK*count','deathrattle':'External bloodline consumer required for lord; no generic fake suicide or empty death Buff','attributes':'Actual source/recipient aura-member and child identities drive pure attributes.effective; final merged content MUST bind_recipients to preserve explicit original attribute rule'},'pending': ['bloodline deathrattle source merge'] if is_lord else [],'whole_consumer_complete':not is_lord,'client_verified':False}},'entities':[],'abilities':[],'buffs':[deepcopy(bloodsucker_mark)],'rules':[],'selectors':[],'projectiles':[]}
 def rule(name,contract,provider,params=None,meta=None):return {'id':'rule/'+PREFIX+name,'kind':'rule','contract':contract,'parameters':params or {},'implementation':{'type':'provider','provider':provider},'metadata':meta or {}}
 p['rules']=[rule('blood_eligibility','targeting.eligibility','source.ch10.remaining.eligible',{'bloodsucker_required':True,'bloodsucker_mark':MARK}),rule('eligibility','targeting.eligibility','source.ch10.remaining.eligible'),rule('motion','projectile.trajectory','source.ch10.remaining.motion'),rule('collision','projectile.collision','model.projectile.collision'),rule('supply_ep','damage.request','source.ch10.remaining.ep',meta={'input_bindings':{'attack':{'entity':'source','attribute':'atk'}}}),{'id':'rule/'+PREFIX+'not_silenced','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'12 not in inputs.status.abnormal_flags'}}]
 def eligibility(c,blood=False):return {'rule':'rule/'+PREFIX+('blood_eligibility' if blood else 'eligibility'),'parameters':{'source_configuration':c,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':DEFAULT_STATE}}
 aura_selector='selector/'+PREFIX+local+'_aura';p['selectors'].append({'id':aura_selector,'kind':'selector','region':{'type':'all'},'filters':[{'state':'alive'}],'eligibility':eligibility(aura_cfg,True)})
 p['buffs'] += [{'id':parent,'kind':'buff','aura':{'selector':aura_selector,'buff':child},**({'active_rule':'rule/'+PREFIX+'not_silenced'} if not is_lord else {})},{'id':child,'kind':'buff','stacking':{'mode':'independent'},**({} if is_lord else {'modifiers':[{'attribute':'atk','layer':'direct_ratio','value':.1}],'damage_hooks':[{'phase':'before','rule':'rule/'+PREFIX+'supply_ep','group':'ch10_supply_ep'}]})}]
 attrs={'max_hp':a['maxHp'],'atk':a['atk'],'def':a['def'],'mres':a['magicResistance'],'move_speed':a['moveSpeed'],'attack_speed':a['attackSpeed'],'attack_speed_ratio':1,'base_attack_time':a['baseAttackTime'],'attack_interval':a['baseAttackTime'],'mass_level':a['massLevel'],'block_cost':1}
 p['entities']=[{'id':body,'kind':'entity','tags':['enemy',local],'components':{'attributes':{'base':attrs},'resources':{'hp':{'role':'health','initial':a['maxHp'],'capacity':a['maxHp']}},'selection_state':{'side':1,'category':1,'motion':1,'unit_type':2},'spatial':{'motion_mode':0},'buffs':{'initial':[parent]},'abilities':[normal],'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':native.get('lifePointReduce',1)}}}]
 selector='selector/'+PREFIX+local+'_normal'
 if is_lord:p['selectors'].append({'id':selector,'kind':'selector','region':{'type':'all','blocked_only':True},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
 else:p['selectors'].append({'id':selector,'kind':'selector','region':{'type':'radius','radius':native['rangeRadius']},'filters':[{'state':'alive'}],'limit':1,'eligibility':eligibility(cfg)})
 effect={'op':'damage','damage_type':'physical','scale':1}
 if not is_lord:
  projectile='projectile/'+PREFIX+'supply';effect['projectile_definition']=projectile;p['projectiles']=[{'id':projectile,'kind':'projectile','motion':{'rule':'rule/'+PREFIX+'motion','parameters':{'mode':'homing','speed':10}},'collision':{'rule':'rule/'+PREFIX+'collision','parameters':{'enabled':False}},'lifetime_seconds':5,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'completion_blocking':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}]
 p['abilities']=[{'id':normal,'kind':'ability','activation':{'mode':'automatic_attack','interval_seconds':a['baseAttackTime']},'selector':selector,'duration_seconds':binding['duration']['seconds'],'timeline':[{'at_seconds':binding['events'][0]['seconds'],'effect':effect}],'metadata':{'source_attack':attack}}]
 return bind_recipients(p)
