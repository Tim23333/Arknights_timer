"""Current-wave ownership, external acknowledgement and zero-HP life preserved."""
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from tools.candidates.chapter07_foundation_v1.test_finish_timeline_wave_v1 import package,EFFECT


def test_old_wave_member_cannot_release_the_next_wave():
    s=Engine.create(Compiler().compile(package()))
    s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=2)
    s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=16)
    s.advance(17)
    assert any(e['type']=='timeline.finish_rejected' and e['time']==16 for e in s.session.events)
    assert sum(e['type']=='timeline.finish_requested' for e in s.session.events)==1


def test_current_wave_ack_control_remains_blocking_after_enemy_clear_request():
    p=package();p['controls']=[{'id':'control/wave/ack','kind':'control','clock_policy':'logical',
        'ack_policy':'external','steps':[{'kind':'ack','key':'wave/explicit'}]}]
    p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append(
        {'kind':'control','definition':'control/wave/ack','instanceAlias':'ack',
         'managed':True,'blocks_wave':True,'blocks_fragment':False})
    s=Engine.create(Compiler().compile(p))
    s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=2)
    s.advance(12);assert s.ctx.state()['timeline']['wave_index']==0
    waiting=next(e for e in s.session.events if e['type']=='control.awaiting_ack')
    s.submit({'action':'control_ack','control':waiting['payload']['control'],'step':waiting['payload']['step']},at=12)
    s.advance(6)
    assert s.ctx.alive('next') and s.ctx.state()['timeline']['wave_index']==1


def test_actual_rebirth_waiting_source_finishes_wave_without_death_or_HPgrant():
    p=package();unit=p['entities'][0];unit['components']['attributes']['base'].update({'def':0,'mres':0});unit['tags']=['wave_source'];unit['components']['rebirth']={
        'resource':'hp','max_count':1,'delay_seconds':60,'restore_ratio':1,
        'restore_rule':'rule/wave/restore','on_begin':[deepcopy(EFFECT)]}
    p['rules']=[{'id':'rule/wave/restore','kind':'rule','contract':'resource.recovery',
        'implementation':{'type':'expression','expression':'inputs.parameters.capacity*inputs.parameters.ratio'}}]
    p['abilities'].append({'id':'ability/wave/kill','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/wave/source','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':0,'additions':100}}]})
    p['selectors']=[{'id':'selector/wave/source','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'wave_source'}],'limit':1}]
    controller={'id':'unit/wave/controller','kind':'entity','components':{'attributes':{'base':{'atk':0}},'abilities':['ability/wave/kill'],'spatial':{}}}
    p['entities'].append(controller);p['scenarioDraft']['initialEntities']=[{'definition':controller['id'],'instanceAlias':'controller','position':{'row':0,'col':0}}]
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'controller','ability':'ability/wave/kill'},at=5);s.advance(17)
    assert s.ctx.resources.current('source','hp')==0 and not s.ctx.active('source') and s.ctx.alive('source')
    assert s.ctx.alive('next') and s.ctx.state()['kills']==s.ctx.state()['leaks']==0
    assert s.ctx.state()['timeline']['wave_index']==1
