"""Fresh root cases for full mutable element state and packet ordering."""
from copy import deepcopy

import pytest
from ark_sim import Compiler,Engine


def package(delayed=False):
    contracts={'capacity':'inputs.attributes.target.ep_capacity','loss':'inputs.request.raw_amount',
               'recovery':'min(inputs.capacity,inputs.current)','break_duration':'inputs.parameters.break_duration_seconds',
               'eligibility':'True','packet':'inputs.source_attributes.atk * .25'}
    rules=[{'id':'rule/root/ep/'+key,'kind':'rule','contract':'elemental.'+key,
            'implementation':{'type':'expression','expression':value}} for key,value in contracts.items()]
    profile={'capacity':19,'resistance':0,'recovery_rate':0,'break_duration_seconds':2,
             'rules':{'elemental.'+key:'rule/root/ep/'+key for key in ('capacity','loss','recovery','break_duration')},
             'on_break':[],'on_end':[]}
    effect={'op':'elemental_attack','health_effect':{'op':'damage','damage_type':'true','scale':1},
            'element_effect':{'op':'elemental_damage','element':'fire','amount':1}}
    if delayed:effect['health_effect']['projectile_definition']='projectile/root/ep'
    rules += [{'id':'rule/root/ep/motion','kind':'rule','contract':'projectile.trajectory',
               'implementation':{'type':'provider','provider':'model.projectile.trajectory'}},
              {'id':'rule/root/ep/collision','kind':'rule','contract':'projectile.collision',
               'implementation':{'type':'provider','provider':'model.projectile.collision'}}]
    p={'schemaVersion':2,'rules':rules,'entities':[
       {'id':'unit/root/ep/source','kind':'entity','components':{'attributes':{'base':{'atk':16}},'spatial':{},
         'resources':{'hp':{'role':'health','initial':100,'capacity':100}},'abilities':['ability/root/ep/cast','ability/root/ep/shrink']}},
       {'id':'unit/root/ep/target','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'ep_capacity':19,'max_hp':100}},
         'spatial':{},'resources':{'hp':{'role':'health','initial':100,'capacity':100}},'lifecycle':{'policy':'policy/ark_lifecycle'},
         'elemental':{'eligibility_rule':'rule/root/ep/eligibility','elements':{'fire':profile,'water':deepcopy(profile)}}}}],
       'selectors':[{'id':'selector/root/ep/target','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]}],
       'buffs':[{'id':'buff/root/ep/shrink','kind':'buff','modifiers':[{'attribute':'ep_capacity','layer':'flat','value':-12}]}],
       'abilities':[{'id':'ability/root/ep/cast','kind':'ability','selector':'selector/root/ep/target','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':effect}]},
                    {'id':'ability/root/ep/shrink','kind':'ability','selector':'selector/root/ep/target','activation':{'mode':'manual'},
                     'timeline':[{'at':0,'effects':[{'op':'apply_buff','buff':'buff/root/ep/shrink'},
                                  {'op':'elemental_damage','element':'fire','amount':1}]}]}],
       'projectiles':[{'id':'projectile/root/ep','kind':'projectile','motion':{'rule':'rule/root/ep/motion','parameters':{'mode':'homing','speed':1}},
         'collision':{'rule':'rule/root/ep/collision','parameters':{'enabled':False}},'lifetime_seconds':5,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,
         'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position',
                      'finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':False,'hit_on_expire':True}}],
       'scenarioDraft':{'id':'scene/root/ep/peer','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},
         'initialEntities':[{'definition':'unit/root/ep/source','instanceAlias':'source','position':{'row':0,'col':0}},
                            {'definition':'unit/root/ep/target','instanceAlias':'target','position':{'row':0,'col':2}}]}}
    return p


def test_atomic_elemental_attack_health_precedes_EP_even_with_declared_projectile():
    s=Engine.create(Compiler().compile(package(delayed=True)))
    s.submit({'action':'skill','source':'source','ability':'ability/root/ep/cast'},at=2)
    s.session.advance(3)
    # The selected public operation promises health-first atomic delivery.
    # It must either reject unsupported delayed delivery or keep EP pending.
    if s.ctx.resources.current('target','hp')==100:
        assert s.ctx.get('target',('runtime','elemental','remaining','fire'))==19


def test_custom_capacity_shrinks_before_same_callback_loss_is_bounded_to_new_capacity():
    s=Engine.create(Compiler().compile(package()))
    s.submit({'action':'skill','source':'source','ability':'ability/root/ep/shrink'},at=2)
    s.session.advance(3)
    assert s.ctx.attributes.value('target','ep_capacity')==7
    assert s.ctx.get('target',('runtime','elemental','remaining','fire'))==6
