"""Source refresh and effect-end ramp reset, old conflicting proofs untouched."""
import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.build_dragon_fire_v3 import OUT,build
from tools.chapter08_boss.dragon_fire_policies_v3 import providers
from tools.chapter08_boss.test_dragon_fire_v2 import package as old_package
from tools.chapter08_boss.build_dragon_fire_v1 import TIMER,CHILD

def package():
    f=old_package();p=json.loads(OUT.read_bytes());p.update({k:f[k] for k in ('entities','selectors','abilities','scenarioDraft')});return p

def proof(p,tmp_path,commands=(0,100),split=90,end=1020):
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    for at in commands:s.submit({'action':'skill','source':'source','ability':'ability/ch8/fire/apply'},at=at)
    s.advance(split);cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(end-split);r.advance(end-split);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events);return s

def test_source_rebuild_and_existing_parent_refresh1015_keepchild_cursor(tmp_path):
    assert json.loads(OUT.read_bytes())==build();s=proof(package(),tmp_path)
    applied=[e for e in s.session.events if e['type']=='buff.applied'];assert [(e['time'],e['payload']['buff']) for e in applied]==[(0,CHILD),(0,TIMER),(100,TIMER)]
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==list(range(30,991,30))
    assert [e['payload']['amount'] for e in hits]==[50+6*n for n in range(1,31)]+[230,230,230]

def test_effectgap_reapply930_resetsretainedchild_notdamage230(tmp_path):
    s=proof(package(),tmp_path,commands=(0,930),split=900,end=1030)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [(e['time'],e['payload']['amount']) for e in hits][-3:]==[(960,56),(990,62),(1020,68)]
    child=[e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==CHILD];assert len(child)==2 and child[0]['payload']['instance']==child[1]['payload']['instance']
    inst=next(i for i in s.ctx.get('target',('buffs','instances')) if i['definition']==CHILD);assert inst['started_at']==930 and inst['generation']==2 and inst['stacks']==1

def test_refresh_withtarget_resist_halved915duration_doesnot_add_time(tmp_path):
    p=package();p['entities'][1]['components']['attributes']['base']['one_minus_status_resistance']=.5
    s=proof(p,tmp_path,commands=(0,100),split=90,end=580)
    assert len([e for e in s.session.events if e['type']=='damage.accepted'])==18
    assert not any(i['definition']==TIMER for i in s.ctx.get('target',('buffs','instances')))

def test_second_caster_extends_sharedtimer_child_max1(tmp_path):
    p=package();p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch8/fire/source','instanceAlias':'second','position':{'row':0,'col':0}})
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg)
    s.submit({'action':'skill','source':'source','ability':'ability/ch8/fire/apply'},at=0);s.submit({'action':'skill','source':'second','ability':'ability/ch8/fire/apply'},at=100)
    s.advance(200);cp=tmp_path/'multi.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg);s.advance(100);r.advance(100);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    rows=s.ctx.get('target',('buffs','instances'));assert len(rows)==2 and {i['definition'] for i in rows}=={TIMER,CHILD}
    assert next(i for i in rows if i['definition']==TIMER)['expires_at']==1015
