"""Actual native-shaped FIRE callback: RES debuff then no-source arts1200."""
from ark_sim import Compiler,Engine


def package():
    rules=[]
    for name,expression in {'capacity':'inputs.parameters.capacity','loss':'inputs.request.raw_amount',
        'recovery':'min(inputs.capacity,inputs.current)','break_duration':'inputs.parameters.break_duration_seconds',
        'eligibility':'True','packet':'inputs.source_attributes.atk * .06'}.items():
        rules.append({'id':'rule/fire/'+name,'kind':'rule','contract':'elemental.'+name,
                      'implementation':{'type':'expression','expression':expression}})
    rules.append({'id':'rule/fire/no_source','kind':'rule','contract':'damage.pipeline',
        'implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount*(1-inputs.effect.resistance*.01),'allocations':[],'events':[]}"}],'output':'nodes.result'},
        'metadata':{'input_bindings':{'resistance':{'entity':'target','attribute':'mres'}}}})
    no_source={'op':'no_source_damage','damage_type':'arts','attack_type':'NORMAL','fixed_amount':1200,
        'damage_without_modify':False,'ignore_for_sp':False,'node_is_env_damage':False,'env_blackboard_injected':False,
        'environmental':False,'origin':{'reference':'C9/source/ep_break_fire_char'},'rules':{'damage.pipeline':'rule/fire/no_source'}}
    profile={'capacity':7.5,'resistance':0,'recovery_rate':0,'break_duration_seconds':10,
        'rules':{'elemental.'+key:'rule/fire/'+key for key in ('capacity','loss','recovery','break_duration')},
        'on_break':[{'op':'apply_buff','buff':'buff/fire/mres_minus20'},no_source],'on_end':[{'op':'remove_buff','buff':'buff/fire/mres_minus20'}]}
    return {'schemaVersion':2,'rules':rules,'buffs':[{'id':'buff/fire/mres_minus20','kind':'buff','modifiers':[{'attribute':'mres','layer':'flat','value':-20}]}],
        'entities':[{'id':'unit/fire/source','kind':'entity','components':{'attributes':{'base':{'atk':500}},'spatial':{},
          'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':['ability/fire/packet']}},
          {'id':'unit/fire/receiver','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':3000,'atk':0,'def':913,'mres':40}},
           'resources':{'hp':{'initial':3000,'capacity':3000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},
           'elemental':{'elements':{'fire':profile},'eligibility_rule':'rule/fire/eligibility'}}}],
        'selectors':[{'id':'selector/fire/receiver','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}]}],
        'abilities':[{'id':'ability/fire/packet','kind':'ability','selector':'selector/fire/receiver','activation':{'mode':'manual'},
          'timeline':[{'at':0,'effect':{'op':'elemental_damage','element':'fire','amount_rule':'rule/fire/packet','parameters':{}}}]}],
        'scenarioDraft':{'id':'scene/fire/callback','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},
          'initialEntities':[{'definition':'unit/fire/source','instanceAlias':'source','position':{'row':0,'col':0}},
                             {'definition':'unit/fire/receiver','instanceAlias':'receiver','position':{'row':0,'col':1}}]}}


def test_FIRE_callback_has_real_None_source_and_debuff_before1200Arts():
    s=Engine.create(Compiler().compile(package()))
    s.submit({'action':'skill','source':'source','ability':'ability/fire/packet'},at=2)
    s.session.advance(3)
    assert s.ctx.resources.current('receiver','hp')==2040
    hit=next(event['payload'] for event in s.session.events if event['type']=='damage.accepted')
    assert hit['source'] is None and hit['attack_type']=='NORMAL' and hit['amount']==960
    assert s.ctx.attributes.value('receiver','mres')==20
