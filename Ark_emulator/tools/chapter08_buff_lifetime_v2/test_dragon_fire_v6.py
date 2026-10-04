"""Actual source counter corrected: parent608 expiry, child packet600 last."""
import json
from tools.chapter08_buff_lifetime_v2.test_clock_v1 import ROOT,CAND
from tools.chapter08_buff_lifetime_v2.build_dragon_fire_v6 import OUT,build
from tools.chapter08_buff_lifetime.policies_v1 import providers as life
from tools.chapter08_boss.dragon_fire_policies_v3 import providers as fire
from tools.chapter08_boss.test_dragon_fire_v2 import package as old
from tools.chapter08_boss.build_dragon_fire_v1 import TIMER
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

def test_real30_5_parent_midlife_resistance_changes_remaining_notchild1s(tmp_path):
    assert json.loads(OUT.read_bytes())==build();fixture=old();p=json.loads(OUT.read_bytes());p.update({k:fixture[k] for k in ('entities','abilities','selectors','scenarioDraft')})
    p['entities'][1]['components']['attributes']['base']['one_minus_status_resistance']=1
    p['buffs'].append({'id':'buff/author/dynamicresist','kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'final_ratio','value':-.5}]})
    p['entities'][1]['components']['abilities']=['ability/author/resist'];p['abilities'].append({'id':'ability/author/resist','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'self','buff':'buff/author/dynamicresist'}]},'timeline':[]})
    reg={**fire(),**life()};program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.submit({'action':'skill','source':'source','ability':'ability/ch8/fire/apply'},at=0);s.submit({'action':'skill','source':'target','ability':'ability/author/resist'},at=300)
    s.advance(301);cp=tmp_path/'dynamic301.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(319);r.advance(319);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in packets]==list(range(30,601,30))
    assert [e['payload']['amount'] for e in packets]==[50+6*n for n in range(1,21)]
    assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==TIMER]==[608]
    assert s.ctx.resources.current('target','hp')==7740
