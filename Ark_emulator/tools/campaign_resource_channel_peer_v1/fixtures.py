"""Independent generic fixtures; no author imports and no simulation at import."""
from copy import deepcopy
SENDER='unit/peer/channel_sender';TARGET='unit/peer/channel_target'
ABILITY='ability/peer/channel';PROFILE='attachment/peer/resource';RESOURCE='battery_q'
def motion(inputs,params,context):
    return {'position':dict(inputs['target']['components']['spatial']['position']),'reached':True,'motion_state':{}}
def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,'peer.resource.motion':{'callable':motion,'version':'first-real-step-arrival-v1'}}
def package(delta=7,initial=11,capacity=23,duration=3.4,interval=.4,freeze=False,maximum=None):
    sender={'id':SENDER,'kind':'entity','tags':['player','peer_sender'],'components':{'attributes':{'base':{'max_hp':503,'atk':13,'def':17}},'resources':{'hp':{'role':'health','initial':503,'capacity':503}},'spatial':{},'deployable':{'terrain':'ground','base_cost':0,'capacity':1,'cooldown_seconds':0},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'abilities':[ABILITY]}}
    target={'id':TARGET,'kind':'entity','tags':['player','peer_recipient'],'components':{'attributes':{'base':{'max_hp':607,'def':21}},'resources':{'hp':{'role':'health','initial':607,'capacity':607},RESOURCE:{'initial':initial,'capacity':capacity,**({'recovery_freeze_rule':'rule/peer/frozen'} if freeze else {})}},'spatial':{},'deployable':{'terrain':'ground','base_cost':0,'capacity':1,'cooldown_seconds':0},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1}}}
    return {'schemaVersion':2,'definitions':[sender,target,
      {'id':'rule/peer/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'peer.resource.motion'}},
      {'id':'rule/peer/frozen','kind':'rule','contract':'resource.recovery_freeze','metadata':{'recovery_freeze_authority':'final_override'},'implementation':{'type':'expression','expression':'True'}},
      {'id':'buff/peer/held','kind':'buff','modifiers':[{'attribute':'def','layer':'flat','value':3}]},
      {'id':'buff/peer/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}},
      {'id':'selector/peer/recipient','kind':'selector','region':{'type':'all'},'filters':[{'tag':'peer_recipient'},{'state':'alive'}],'limit':1},
      {'id':PROFILE,'kind':'attachment','duration_seconds':duration,'flight_lifetime_seconds':.2,'step_interval_seconds':1/30,'refresh_interval_seconds':.7,'hit_interval_seconds':interval,'motion':{'rule':'rule/peer/motion','parameters':{}},'target_buff':'buff/peer/held','effect':{'op':'modify_resource','resource':RESOURCE,'delta':delta,'parameters':{'respect_recovery_freeze':True}},'damage_integral':False,'completion_blocking':True,'force_reach_on_timeout':True,'source_cancel_flags':[12,0],'ignored_owned_source_flags':[],'lifecycle':{'source_invalid':'cancel','target_invalid':'cancel','source_hidden':'cancel','target_hidden':'cancel'},'max_packets':maximum,'source_recovery_buff':None,'recovery_on':[]},
      {'id':ABILITY,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/recipient','wait_for_channels':True,'timeline':[{'at':0,'effect':{'op':'begin_attachment','attachment':PROFILE}}]}],
      'scenarioDraft':{'id':'scene/peer/resource_channel','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'resources':{'dp':{'initial':47,'capacity':71}},'initialEntities':[{'definition':SENDER,'instanceAlias':'sender','position':{'row':1,'col':1},'deployed':True},{'definition':TARGET,'instanceAlias':'recipient','position':{'row':1,'col':3},'deployed':True}],'commands':[{'at':1,'action':'skill','source':'sender','ability':ABILITY}]}}
def terminal_package():
    p=package(capacity=101);next(d for d in p['definitions'] if d['id']==PROFILE)['completion_blocking']=False
    p['definitions'].extend([
      {'id':'unit/peer/killer','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':317,'atk':10}},'resources':{'hp':{'role':'health','initial':317,'capacity':317}},'spatial':{},'abilities':['ability/peer/end']}},
      {'id':'unit/peer/managed','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':1,'def':0,'mres':0}},'resources':{'hp':{'role':'health','initial':1,'capacity':1}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
      {'id':'selector/peer/managed','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1},
      {'id':'ability/peer/end','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/managed','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}])
    scene=p['scenarioDraft'];scene['initialEntities'].append({'definition':'unit/peer/killer','instanceAlias':'killer','position':{'row':2,'col':0}});scene['commands'].append({'at':20,'action':'skill','source':'killer','ability':'ability/peer/end'});scene['resources']={'life':{'initial':99999,'capacity':99999}};scene['objectives']={'type':'waves','life_resource':'life'};scene['timeline']={'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/peer/managed','position':{'row':2,'col':4}},'count':1,'managed':True,'blocks_wave':True}]}]}]}
    return p
