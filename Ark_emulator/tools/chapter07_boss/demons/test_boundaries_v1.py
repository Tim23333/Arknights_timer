"""Typed caster target gates and restoration to source default mode."""
import pytest
from tools.chapter07_boss.demons.test_modules_v2 import package,make,change,ev,packets,NAMES
from ark_sim import Compiler,Engine
@pytest.mark.parametrize('name',NAMES[1:])
@pytest.mark.parametrize('field,value',[('motion',2),('camouflage',True),('target_free',True)])
def test_native_caster_ground_camo_and_targetfree_gate_no_fake_normal(name,field,value):
 p=package(name,outer=True);p['entities'][1]['components']['selection_state'][field]=value;s=Engine.create(Compiler().compile(p),seed=7178);s.session.advance(1)
 assert not packets(s) and len(ev(s,'area.resolved'))==1 and not ev(s,'area.resolved')[0]['payload']['members']
 assert len(ev(s,'ability.started'))==1 and '/immo0' in ev(s,'ability.started')[0]['payload']['ability']
@pytest.mark.parametrize('name',NAMES[1:])
def test_public_restore_default_mode_preserves_natural_cooldown_and_drops_outer(name):
 s=make(name,outer=True);change(s,1,2);change(s,0,200);s.session.advance(302)
 atk=350 if name==NAMES[1] else 450
 assert [t for t,_ in packets(s) if t>=200]==[300,300]
 assert all(d==atk*.75 for t,d in packets(s) if t>=200)
 assert s.ctx.get('enemy',('behavior','state'))=='mode0'
