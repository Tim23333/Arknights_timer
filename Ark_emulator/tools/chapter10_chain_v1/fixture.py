"""Small public-cast finite-chain probes, independent of whole-stage inputs."""
from copy import deepcopy


def package():
    from ark_sim.domains.selection import DEFAULT_STATE
    rules=[]
    def rule(key,contract,expression=None,provider=None):
        rid='rule/chain/probe/'+key
        rules.append({'id':rid,'kind':'rule','contract':contract,'implementation':
            {'type':'expression','expression':expression} if expression else {'type':'provider','provider':provider}})
        return rid
    motion=rule('motion','projectile.trajectory',provider='model.projectile.trajectory')
    collision=rule('collision','projectile.collision',provider='model.projectile.collision')
    eligible=rule('eligible','targeting.eligibility',provider='model.targeting.eligibility')
    erules={}
    for k,expr in [('capacity','inputs.parameters.capacity'),('loss','inputs.request.raw_amount'),
                   ('recovery','inputs.current'),('break_duration','inputs.parameters.break_duration_seconds')]:
        erules['elemental.'+k]=rule('ep_'+k,'elemental.'+k,expr)
    epeligible=rule('ep_eligible','elemental.eligibility','True')
    packet=rule('ep_packet','elemental.packet','inputs.source_attributes.atk * inputs.request.parameters.ratio * inputs.request.parameters.attack_scale')
    cfg={'_targetSide':2,'_targetMotion':3,'_targetCategory':1,'_ignoreTargetFree':0,
         '_onlyIgnoreSomeOfTargetFreeCase':0,'_abnormalFlag':0,'_abnormalCombo':0,
         '_ignoreAllyTargetFree':0,'_ignoreHealFree':0,'_ignoreMotionMode':0,
         '_forceIgnoreCamouflage':0,'_needProfessionMask':0,'_professionMask':0,
         '_excludeSomeAbnormalFlags':0,'_excludeAbnormalFlag':0,'_checkUnitType':0,'_unitTypeMask':0}
    qualification={'rule':eligible,'parameters':{'source_configuration':cfg,
        'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}
    effect={'op':'elemental_attack','health_effect':{'op':'damage','damage_type':'arts','scale':1,
        'projectile_definition':'projectile/chain/probe','read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}},
        'element_effect':{'op':'elemental_damage','element':'DARK','amount_rule':packet,
                          'parameters':{'ratio':.3,'attack_scale':1}}}
    profile={'capacity':10000,'resistance':0,'recovery_rate':0,'break_duration_seconds':1,
             'rules':erules,'on_break':[],'on_end':[]}
    source={'id':'unit/chain/source','kind':'entity','tags':['enemy'],'components':{
        'attributes':{'base':{'max_hp':10000,'atk':550,'def':0,'mres':0,'attack_interval':4,'attack_speed_ratio':1}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'selection_state':{'side':1,'category':1,'motion':1},'spatial':{},
        'abilities':['ability/chain/probe'],'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    target={'id':'unit/chain/target','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'max_hp':10000,'def':0,'mres':0}},
        'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'selection_state':{'side':0,'category':1,'motion':1},'spatial':{},
        'elemental':{'eligibility_rule':epeligible,'elements':{'DARK':profile}},
        'lifecycle':{'policy':'policy/ark_lifecycle'}}}
    return {'schemaVersion':2,'rules':rules,'entities':[source,target],
        'selectors':[{'id':'selector/chain/first','kind':'selector','region':{'type':'radius','radius':2.2},
                      'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'eligibility':qualification},
                     {'id':'selector/chain/next','kind':'selector','region':{'type':'radius','radius':1.6},
                      'filters':[{'tag':'player'},{'state':'alive'}],'limit':1,'eligibility':qualification}],
        'projectiles':[{'id':'projectile/chain/probe','kind':'projectile',
            'motion':{'rule':motion,'parameters':{'mode':'homing','speed':15}},
            'collision':{'rule':collision,'parameters':{'enabled':False}},'lifetime_seconds':10,
            'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,
            'attach_at_launch':False,'completion_blocking':False,
            'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'cancel',
                'target_hidden':'cancel','finish_on_reach':True,'hit_on_reach':True,
                'force_reach_on_expire':True,'hit_on_expire':True},
            'chain':{'selector':'selector/chain/next','maximum_targets':4,'attenuation':.85,
                'selection_origin':'impact_position','no_repeat':True,'lifetime':'whole_chain',
                'scale_fields':[['health_effect','scale'],['element_effect','parameters','attack_scale']]}}],
        'abilities':[{'id':'ability/chain/probe','kind':'ability','activation':{'mode':'manual'},
            'selector':'selector/chain/first','parameters':{'wait_for_projectiles':True},
            'duration_seconds':66/30,'timeline':[{'at':37,'effect':effect}]}],
        'scenarioDraft':{'id':'scenario/chain/probe','ruleset':'ruleset/ark_standard',
            'map':{'rows':5,'cols':10},'initialEntities':[
                {'definition':'unit/chain/source','instanceAlias':'source','position':{'row':2,'col':1}},
                *[{'definition':'unit/chain/target','instanceAlias':'target'+str(i),
                   'position':{'row':2,'col':2+i}} for i in range(5)]]}}
