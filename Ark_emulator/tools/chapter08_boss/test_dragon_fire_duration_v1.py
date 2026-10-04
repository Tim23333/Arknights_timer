"""Real source Attribute26 initial-duration and independent nonresisted child."""
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.test_dragon_fire_v2 import package as old_package
from tools.chapter08_boss.build_dragon_fire_v2 import OUT,build
from tools.chapter08_boss.dragon_fire_policies_v2 import providers
from tools.chapter08_boss.build_dragon_fire_v1 import TIMER,CHILD

def package(multiplier=.5):
    f=old_package();p=json.loads(OUT.read_bytes());p.update({k:f[k] for k in ('entities','selectors','abilities','scenarioDraft')})
    p['entities'][1]['components']['attributes']['base']['one_minus_status_resistance']=multiplier
    return p

def proof(p,tmp_path,end=500):
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.submit({'action':'skill','source':'source','ability':'ability/ch8/fire/apply'},at=0)
    s.advance(300);cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-300);r.advance(end-300);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    return s

def test_rebuild_and_half_duration458_first15packets_only(tmp_path):
    assert json.loads(OUT.read_bytes())==build();s=proof(package(),tmp_path)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==list(range(30,451,30))
    assert [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,16)]
    assert not any(i['definition']==TIMER for i in s.ctx.get('target',('buffs','instances'),[]))
    assert any(i['definition']==CHILD and i['expires_at'] is None for i in s.ctx.get('target',('buffs','instances'),[]))

def test_actual_modifier_duration26_flat_minus_half(tmp_path):
    p=package(1);p['buffs'].append({'id':'buff/ch8/fire/author_resistance','kind':'buff',
        'modifiers':[{'attribute':'one_minus_status_resistance','layer':'flat','value':-.5}]})
    p['entities'][1]['components']['buffs']={'initial':['buff/ch8/fire/author_resistance']};s=proof(p,tmp_path)
    assert len([e for e in s.session.events if e['type']=='damage.accepted'])==15

def test_source_minimum_clamp_makes1tick_timer_no_first_tick30_damage(tmp_path):
    s=proof(package(0),tmp_path)
    assert not [e for e in s.session.events if e['type']=='damage.accepted']
    assert len([e for e in s.session.events if e['type']=='buff.applied'])==2

def test_invalid_duration_value_atomic_pure_application():
    from tools.chapter08_boss.dragon_fire_policies_v2 import apply
    with pytest.raises(ValueError,match='finite'):apply({'instances':[],'attributes':{'one_minus_status_resistance':True}},
        {'timer':TIMER,'child':CHILD,'duration_attribute':'one_minus_status_resistance','minimum_multiplier':.001,'maximum_multiplier':1000,'duration':30.5},{'time':0})
