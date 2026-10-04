"""Actual source tile skill/cast ordering/immunity; no stage completion claim."""
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
from tools.chapter06_boss.frstar2.test_module import package,kill,deploy,hp,events
from tools.chapter06_boss.frstar2.build_module import ROOT,COLD,UID,N,B,I,SUM
from tools.chapter06.cold.policies import providers

def tile_package():
    p=package(target=False)
    p['scenarioDraft']['map']['tiles']=[{'buildableType':1 if (r,c) in [(2,1),(1,2),(2,4)] else 0,'passableMask':1} for r in range(5) for c in range(9)]
    return p
def make(p):return Engine.create(Compiler(providers=providers()).compile(p,packages=[COLD]),seed=6216,providers=providers())

@pytest.mark.parametrize('reborn,count',[(False,2),(True,3)])
def test_real_ice_initial35_native55_event_and_phase_count2_or3(reborn,count):
    s=make(tile_package())
    if reborn:kill(s,5)
    start=1355 if reborn else 1050
    s.session.advance(start)
    assert not [e for e in events(s,'ability.started') if e['payload']['ability'] in I]
    s.session.advance(1)
    assert [e['time'] for e in events(s,'ability.started') if e['payload']['ability']==I[int(reborn)]]==[start]
    s.session.advance(54)
    assert not [e for e in s.session.world.entities() if 'sealed_floor' in e.get('tags',[])]
    s.session.advance(1)
    floors=[e for e in s.session.world.entities() if 'sealed_floor' in e.get('tags',[])]
    assert len(floors)==count and all(not s.ctx.selectable(e['id']) for e in floors)
    positions={(e['components']['spatial']['position']['row'],e['components']['spatial']['position']['col']) for e in floors}
    assert positions<={(2,1),(1,2),(2,4)}

def test_actual_shield_capture_then_public_late_occupant_instantkill_allows_rebirth_policy():
    s=make(tile_package());s.session.advance(1051)
    cast=next(c for c in s.ctx.get('boss',('runtime','casts'),{}).values() if c['ability']==I[0]);cell=cast['tile_targets'][0]
    s.submit({'action':'deploy','definition':'unit/test/frstar2/player','alias':'late','position':cell},at=1052)
    s.session.advance(55)
    assert not s.ctx.alive('late') and hp(s,'late')==0
    assert len([e for e in events(s,'entity.died') if e['payload'].get('target')==s.session.world.resolve('late') or e['payload'].get('source')==s.session.world.resolve('late')])==1

def test_public_repeated_cold_honors_frozen_immunity_but_retains_real_cold_aspeed():
    p=package();p['entities'][0]['tags'].append('cold_receiver');p['entities'][1]['tags'].remove('cold_receiver')
    controller=next(u for u in p['entities'] if u['id']=='unit/test/frstar2/controller');controller['components']['abilities']+=['ability/ch6/cold/apply5']
    s=make(p)
    for tick in (0,1):s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=tick)
    s.session.advance(2)
    state=s.ctx.spatial.selection_state('boss',DEFAULT_STATE)
    assert 23 in state['abnormal_flags'] and 16 not in state['abnormal_flags']
    assert s.ctx.attributes.value('boss','attack_speed_ratio')==pytest.approx(.7)
    assert s.ctx.buffs.controls('boss')['abilities'] and s.ctx.buffs.controls('boss')['attack']


def test_controlled_simultaneous_skill_readiness_uses_source_priority_not_array_order():
    p=tile_package()
    for ability in p['abilities']+p['definitions']:
        if ability.get('id') in I+B:ability['initial_cooldown_seconds']=0
    p['scenarioDraft']['map']['tiles'][2*9+3]['buildableType']=1
    s=make(p);deploy(s);s.session.advance(1)
    accepted=events(s,'ability.arbitrated')
    assert len(accepted)==1 and accepted[0]['payload']['ability']==I[0] and accepted[0]['payload']['priority']==2
    s.session.advance(89)
    assert len(events(s,'ability.arbitrated'))==1
    s.session.advance(2)
    assert events(s,'ability.arbitrated')[1]['payload']['ability']==B[0]


@pytest.mark.parametrize('flag',[0,12,16,25])
def test_public_control_buff_consumer_respects_each_true_native_intrinsic_immunity(flag):
    p=package();rule='rule/test/frstar2/control'+str(flag);buff='buff/test/frstar2/control'+str(flag);ability='ability/test/frstar2/control'+str(flag)
    p['rules'].append({'id':rule,'kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':str(flag)+' not in inputs.status.abnormal_immunes'}})
    p['buffs'].append({'id':buff,'kind':'buff','duration_seconds':10,'active_rule':rule,'control_rule':rule,'selection_flags':{'abnormal_flags':[flag]},'control':{'move':False,'attack':False,'abilities':False,'interrupt':True}})
    p['abilities'].append({'id':ability,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/test/frstar2/boss','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':buff}}]})
    controller=next(u for u in p['entities'] if u['id']=='unit/test/frstar2/controller');controller['components']['abilities'].append(ability)
    s=make(p);s.submit({'action':'skill','source':'controller','ability':ability},at=0);deploy(s);s.session.advance(32)
    state=s.ctx.spatial.selection_state('boss',DEFAULT_STATE)
    assert flag not in state['abnormal_flags'] and s.ctx.buffs.controls('boss')['attack'] and s.ctx.buffs.controls('boss')['abilities']
    assert any(e['payload']['ability']==N[0] for e in events(s,'ability.started'))
