"""New independent source bloodline parent-death scenes, no author assertion."""
import copy
def package(policy='dead'):
    from tools.chapter10_bloodline_v1.build import build,entity_id
    p=build('enemy_1222_dpvt');source=entity_id('enemy_1222_dpvt')
    receiver={'id':'unit/lookup/observer','kind':'entity','tags':['player','observer'],'components':{
      'attributes':{'base':{'max_hp':4711,'atk':99999,'def':127,'mres':19}},'resources':{'hp':{'role':'health','initial':4711,'capacity':4711}},
      'spatial':{},'selection_state':{'side':0,'category':1,'motion':1},'abilities':['ability/lookup/terminate'], 'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    keeper=copy.deepcopy(receiver);keeper['id']='unit/lookup/keeper';keeper['tags']=['enemy','keeper'];keeper['components']['selection_state']['side']=1;keeper['components']['abilities']=[]
    p['entities'].extend([receiver,keeper]);p['selectors'].append({'id':'selector/lookup/parent','kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['definition_id'],'equals':source}},{'state':'alive'}],'limit':1})
    effect={'op':'damage','damage_type':'true','scale':1} if policy=='dead' else {'op':'retire','parameters':{'reason':'withdrawn'}}
    p['abilities'].append({'id':'ability/lookup/terminate','kind':'ability','activation':{'mode':'manual'},'selector':'selector/lookup/parent','timeline':[{'at':0,'effect':effect}]})
    route={'motionMode':'WALK','startPosition':{'row':2,'col':1},'endPosition':{'row':2,'col':10},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':6,'position':{'row':2,'col':1}}]}
    keep={'motionMode':'WALK','startPosition':{'row':6,'col':1},'endPosition':{'row':6,'col':10},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':7,'position':{'row':6,'col':1}}]}
    p['scenarioDraft']={'id':'scene/lookup/'+policy,'ruleset':'ruleset/ark_standard','map':{'rows':9,'cols':12},
      'resources':{'life':{'initial':937,'capacity':937}},'objectives':{'type':'waves','life_resource':'life'},
      'initialEntities':[{'definition':receiver['id'],'instanceAlias':'observer','position':{'row':8,'col':11}}],
      'commands':[{'at':11,'action':'skill','source':'observer','ability':'ability/lookup/terminate'}],
      'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[
        {'kind':'spawn','spawn':{'definition':source,'instanceAlias':'parent','position':{'row':2,'col':1},'route':route},'count':1,'managed':True,'blocks_wave':True},
        {'kind':'spawn','spawn':{'definition':keeper['id'],'instanceAlias':'keeper','position':{'row':6,'col':1},'route':keep},'count':1,'managed':True,'blocks_wave':True}]}]}]}}
    return p
