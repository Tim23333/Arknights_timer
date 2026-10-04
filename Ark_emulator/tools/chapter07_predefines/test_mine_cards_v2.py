"""Public mine deployment uses real stock15, fixed DP5, no character slot."""
import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay

ROOT=Path(__file__).resolve().parents[2]


def package():
    p=json.loads((ROOT/'packages/campaign/chapter07_predefines_consumer/mine.module.v2.json').read_bytes())
    p['scenarioDraft']={'id':'scene/mine/card','ruleset':'ruleset/ark_standard',
        'map':{'rows':1,'cols':2},'objectives':{},'parameters':{'deploy_capacity':0},
        'resources':{'dp':{'initial':20,'capacity':99},'stock_ch7_mine':{'initial':15,'capacity':15}},
        'dependencies':[p['entities'][0]['id']]}
    return p


def test_stock_fixed_fee_max1_zero_capacity_rejection_no_partial_payment():
    s=Engine.create(Compiler().compile(package()),seed=7184)
    uid='unit/ch7/predefined/mine/level1'
    s.submit({'action':'deploy','entity':uid,'row':0,'col':0,'alias':'m1'},at=0)
    s.submit({'action':'deploy','entity':uid,'row':0,'col':1,'alias':'m2'},at=1)
    s.advance(2)
    assert s.ctx.resources.current('system/battle','stock_ch7_mine')==14
    assert s.ctx.resources.current('system/battle','dp')==15
    assert s.ctx.alive('m1')
    assert [e['type'] for e in s.session.events if e['type'].startswith('command.')]==['command.accepted','command.rejected']
    assert s.checkpoint()==replay(s.program,s.export_replay()).checkpoint()


def test_zero_refund_and_exact_retirement_cooldown_before_second_fixed_fee():
    s=Engine.create(Compiler().compile(package()),seed=7185);uid='unit/ch7/predefined/mine/level1'
    s.submit({'action':'deploy','entity':uid,'row':0,'col':0,'alias':'m1'},at=0)
    s.submit({'action':'withdraw','source':'m1'},at=1)
    s.submit({'action':'deploy','entity':uid,'row':0,'col':0,'alias':'tooSoon'},at=210)
    s.submit({'action':'deploy','entity':uid,'row':0,'col':0,'alias':'m2'},at=211)
    s.advance(212)
    assert s.ctx.resources.current('system/battle','stock_ch7_mine')==13
    assert s.ctx.resources.current('system/battle','dp')==10
    assert s.ctx.alive('m2')
    assert any(e['type']=='command.rejected' and e['time']==210 for e in s.session.events)
    assert s.checkpoint()==replay(s.program,s.export_replay()).checkpoint()
