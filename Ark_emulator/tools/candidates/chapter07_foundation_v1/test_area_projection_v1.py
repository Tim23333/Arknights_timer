"""A custom continuous box consumes live typed state without borrowing a provider name."""
import json
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.selection import DEFAULT_STATE,SWITCHES
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def custom_box(inputs,params,context):
    result=[];states=context['area_selection_states'];center=inputs['center_position']
    for actor in inputs['candidates']:
        position=actor['components']['spatial']['position']
        if max(abs(position[k]-center[k]) for k in ('row','col'))>params['half_extent']:continue
        decision=context.calculate('targeting.eligibility',{'source':context['source'],'candidate':actor,
            'selector':{'healing':False},'parameters':params['eligibility']['parameters'],
            'selection_states':{'source':states['source'],'candidate':states['candidates'][str(actor['id'])]}},
            rule_id=params['eligibility']['rule']).value
        if decision['accepted']:result.append(actor['id'])
    return result


def registry():
    return {**BUILTIN_PROVIDERS,'custom/explicit_box':{'callable':custom_box,'version':'1.0.0'}}


def package():
    config={k:False for k in SWITCHES};config.update(_targetSide=2,_targetMotion=1,_targetCategory=1)
    eligibility={'rule':'rule/box/eligibility','parameters':{'source_configuration':config,
        'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)}}
    area={'op':'area','target':'source','center':'source','membership_rule':'rule/box/members',
          'selection_projection':{'defaults':deepcopy(DEFAULT_STATE)},
          'effects':[{'op':'emit','event':'probe.box.member'}]}
    p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},
       'rules':[{'id':'rule/box/eligibility','kind':'rule','contract':'targeting.eligibility',
                 'implementation':{'type':'provider','provider':'model.targeting.eligibility'}},
                {'id':'rule/box/members','kind':'rule','contract':'area.members',
                 'implementation':{'type':'provider','provider':'custom/explicit_box'},
                 'dependencies':['rule/box/eligibility'],'parameters':{'half_extent':1.5,'eligibility':eligibility}}],
       'buffs':[{'id':'buff/box/camo','kind':'buff','selection_flags':{'abnormal_flags':[17]}}],
       'selectors':[{'id':'selector/box/camo','kind':'selector','region':{'type':'all'},'filters':[{'tag':'camo'}]}],
       'abilities':[{'id':'ability/box/fire','kind':'ability','activation':{'mode':'manual'},
                     'timeline':[{'at':10,'effect':area}]}], 'entities':[],
       'scenarioDraft':{'id':'scene/custom/box','ruleset':'ruleset/ark_standard','map':{'rows':5,'cols':5},
            'objectives':{},'initialEntities':[],
            'scheduledEffects':[{'at':5,'effect':{'op':'apply_buff','selector':'selector/box/camo','buff':'buff/box/camo'}}]}}
    actors=[('owner',1,2,2),('corner',0,3.5,3.5),('outside',0,3.50001,2),('camo',0,3,2)]
    for alias,side,row,col in actors:
        components={'selection_state':{'side':side,'category':1,'motion':1,'unit_type':1},'spatial':{}}
        if alias=='owner':components['abilities']=['ability/box/fire']
        p['entities'].append({'id':'unit/box/'+alias,'kind':'entity','tags':[alias],'components':components})
        p['scenarioDraft']['initialEntities'].append({'definition':'unit/box/'+alias,'instanceAlias':alias,
                                                      'position':{'row':row,'col':col}})
    return p


def test_live_buff_projection_custom_square_corner_and_CP_head(tmp_path):
    reg=registry();s=Engine.create(Compiler(providers=reg).compile(package()),providers=reg,seed=7196)
    s.submit({'action':'skill','source':'owner','ability':'ability/box/fire'},at=0)
    s.advance(7);cp=tmp_path/'box7.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
    s.advance(7);r.advance(7);assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay(),providers=reg).checkpoint()
    hits=[e for e in s.session.events if e['type']=='probe.box.member']
    assert len(hits)==1 and hits[0]['payload']['target']==s.session.world.resolve('corner')
    assert hits[0]['time']==10


@pytest.mark.parametrize('mutation',['wrong_op','no_rule','bool_defaults','missing_defaults','unknown_field','bool_enum'])
def test_explicit_projection_compile_strict_shape_and_defaults(mutation):
    p=package();effect=p['abilities'][0]['timeline'][0]['effect']
    if mutation=='wrong_op':effect['op']='emit'
    elif mutation=='no_rule':effect.pop('membership_rule')
    elif mutation=='bool_defaults':effect['selection_projection']['defaults']=True
    elif mutation=='missing_defaults':effect['selection_projection']['defaults'].pop('side')
    elif mutation=='unknown_field':effect['selection_projection']['copy_world']=True
    else:effect['selection_projection']['defaults']['motion']=True
    with pytest.raises(ValueError):Compiler(providers=registry()).compile(p)


def test_runtime_dynamic_projection_invalid_rolls_back_events_and_state():
    s=Engine.create(Compiler(providers=registry()).compile(package()),providers=registry())
    effect=deepcopy(package()['abilities'][0]['timeline'][0]['effect']);effect['selection_projection']['defaults']['motion']=True
    before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.effects.execute('owner',[s.session.world.resolve('owner')],effect)
    assert s.checkpoint()==before
