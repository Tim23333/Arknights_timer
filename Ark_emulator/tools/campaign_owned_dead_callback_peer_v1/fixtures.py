"""Independent data-only preparation; final schema/freeze not executed yet."""
from copy import deepcopy
RESOURCE='coil_charge';CAST='ability/peer/captured_hold';BUFF='buff/peer/captured_interrupt'
def actor(id,tags,hp,abilities=(),charge=None):
    resources={'hp':{'role':'health','initial':hp,'capacity':hp}}
    if charge is not None:resources[RESOURCE]={'initial':charge,'capacity':67}
    return {'id':id,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':hp,'atk':1000,'def':0,'mres':0}},'resources':resources,'spatial':{},'selection_state':{'side':0,'category':1,'motion':1,'unit_type':1},'deployable':{'terrain':'ground','base_cost':0,'capacity':1,'cooldown_seconds':0},'abilities':list(abilities),'lifecycle':{'policy':'policy/ark_lifecycle'}}}
def package(delta=-7.25,allow_inactive=True,live_selector=True):
    effect={'op':'modify_resource','resource':RESOURCE,'delta':delta,'target':'selected','selector':'selector/peer/callback_recipients'}
    subscription={'event':'ability.interrupted','condition':'inputs.payload.source == context.owner.id','effects':[effect],'owned_callback':{'mode':'synchronous_interrupt','ability':CAST,'allow_owner_inactive':allow_inactive,'selector_timing':'live_at_event'}}
    p={'schemaVersion':2,'definitions':[
        actor('unit/peer/callback_caster',['player','callback_caster'],503,[CAST]),
        actor('unit/peer/recipientA',['player','callback_recipient'],607,charge=43),
        actor('unit/peer/recipientB',['player','callback_recipient'],709,charge=59),
        actor('unit/peer/callback_killer',['player'],811,['ability/peer/kill_caster']),
        {'id':BUFF,'kind':'buff','events':[subscription]},
        {'id':'selector/peer/callback_recipients','kind':'selector','region':{'type':'all'},'filters':[{'tag':'callback_recipient'},{'state':'alive'}],'limit':1},
        {'id':'selector/peer/callback_caster','kind':'selector','region':{'type':'all'},'filters':[{'tag':'callback_caster'},{'state':'alive'}],'limit':1},
        {'id':CAST,'kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':BUFF,'bind_to_cast':True}]},'selector':'selector/peer/callback_recipients','duration_seconds':6,'timeline':[]},
        {'id':'ability/peer/kill_caster','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/callback_caster','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':1}}]}
    ],'scenarioDraft':{'id':'scene/peer/captured_dead_callback','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'resources':{'dp':{'initial':13,'capacity':29}},'initialEntities':[
        {'definition':'unit/peer/callback_caster','instanceAlias':'caster','position':{'row':1,'col':0},'deployed':True},
        {'definition':'unit/peer/recipientA','instanceAlias':'targetA','position':{'row':1,'col':1},'deployed':True},
        {'definition':'unit/peer/recipientB','instanceAlias':'targetB','position':{'row':1,'col':3},'deployed':True},
        {'definition':'unit/peer/callback_killer','instanceAlias':'killer','position':{'row':2,'col':0},'deployed':True}],
        'commands':[{'at':1,'action':'skill','source':'caster','ability':CAST},*([{'at':5,'action':'withdraw','source':'targetA'}] if live_selector else []),{'at':7,'action':'skill','source':'killer','ability':'ability/peer/kill_caster'}]}}
    return p
