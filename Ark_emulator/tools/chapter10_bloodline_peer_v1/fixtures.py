"""Fresh independent source models; no author test fixture imports."""
from copy import deepcopy
from tools.chapter10_bloodline_v1.build import build_all,entity_id,KEYS

def base():
 p=build_all()
 for a in p['abilities']:a['activation']['condition']='False'
 caster={'id':'unit/independent/bloodline/caster','kind':'entity','tags':['player','caster'],'components':{'attributes':{'base':{'max_hp':34919,'atk':331,'def':919,'mres':57,'block_count':0}},'resources':{'hp':{'role':'health','initial':34919,'capacity':34919}},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'spatial':{},'abilities':[],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(caster);return p

def resistance_scene():
 p=base();initial=[{'definition':p['entities'][-1]['id'],'instanceAlias':'caster','position':{'row':1,'col':1}}];commands=[];schedule=2
 for index,key in enumerate(KEYS):
  body=next(e for e in p['entities'] if e['id']==entity_id(key));tag='independent_target_'+str(index);body['tags'].append(tag);initial.append({'definition':body['id'],'instanceAlias':key,'position':{'row':3,'col':index+2}});sid='selector/independent/'+str(index);p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'all'},'filters':[{'tag':tag}],'limit':1})
  for kind in ['physical','arts','true']:
   aid='ability/independent/'+str(index)+'/'+kind;p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':sid,'timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind,'scale':1}}]});p['entities'][-1]['components']['abilities'].append(aid);commands.append({'at':schedule,'action':'skill','source':'caster','ability':aid});schedule+=2
 p['scenarioDraft']={'id':'scene/independent/bloodline/resistance','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial,'commands':commands};return p

def death_scene():
 p=base();caster=p['entities'][-1];caster['components']['attributes']['base']['atk']=77747;aid='ability/independent/kill_parent';p['selectors'].append({'id':'selector/independent/parent','kind':'selector','region':{'type':'all'},'filters':[{'tag':'independent_parent'}],'limit':1});p['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/independent/parent','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]});caster['components']['abilities']=[aid];parent=next(e for e in p['entities'] if e['id']==entity_id('enemy_1222_dpvt_2'));parent['tags'].append('independent_parent')
 route={'motionMode':'WALK','startPosition':{'row':3,'col':4},'endPosition':{'row':3,'col':11},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':3.0,'position':{'row':3,'col':4}},{'type':'MOVE','time':0.0,'position':{'row':3,'col':7}}]}
 def spawn(definition,alias,position,route=None):
  row={'kind':'spawn','spawn':{'definition':definition,'instanceAlias':alias,'position':position},'count':1,'delay_seconds':0.0,'interval_seconds':1.0,'managed':True,'blocks_wave':True,'blocks_fragment':False}
  if route is not None:row['spawn']['route']=route
  return row
 keeper=deepcopy(caster);keeper['id']='unit/independent/keeper';keeper['tags']=['keeper'];keeper['components']['abilities']=[];keeper['components']['selection_state']['side']=1;p['entities'].append(keeper)
 p['scenarioDraft']={'id':'scene/independent/bloodline/death','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':caster['id'],'instanceAlias':'caster','position':{'row':1,'col':2}}],'commands':[{'at':11,'action':'skill','source':'caster','ability':aid}],'objectives':{'type':'waves','life_resource':'life'},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':0.0,'post_delay_seconds':0.0,'max_wait_seconds':-1.0,'fragments':[{'pre_delay_seconds':0.0,'actions':[spawn(parent['id'],'parent',route['startPosition'],route),spawn(keeper['id'],'keeper',{'row':6,'col':10})]}]}]}};return p

def blocking_scene():
 p=base();blocker=p['entities'][-1];blocker['tags']=['player','blocker'];blocker['components']['attributes']['base']['block_count']=1;blocker['components']['deployable']={'base_cost':0,'terrain':'both','capacity':1};blocker['components']['spatial']['blocking']=True;initial=[{'definition':blocker['id'],'instanceAlias':'blocker','position':{'row':3,'col':4}}]
 for i in range(8):initial.append({'definition':entity_id('enemy_1220_dzoms_2'),'instanceAlias':'sucker'+str(i),'position':{'row':3,'col':4},'route':{'motionMode':'WALK','startPosition':{'row':3,'col':4},'endPosition':{'row':3,'col':11},'checkpoints':[]}})
 p['scenarioDraft']={'id':'scene/independent/bloodline/blocking','ruleset':'ruleset/ark_standard','map':{'rows':8,'cols':12},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':initial};return p
