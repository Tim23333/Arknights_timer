"""Same saved public counter-input, corrected typed source timing only."""
from pathlib import Path
import json,pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.chapter06_boss.frstar2_v2.build_module import ROOT,OUT,UID,N,B
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUT=ROOT/'validation/campaign/chapter06_boss_fullbusy_independent/inputs.json'
def package():
 p=json.loads(INPUT.read_bytes())[0];m=json.loads((OUT/'model.v2.json').read_bytes());defs={d['id']:d for d in p['definitions']}
 for bucket in ['entities','rules','abilities','buffs','selectors','projectiles','behaviors','definitions']:
  for d in m.get(bucket,[]):defs[d['id']]=d
 p['definitions']=list(defs.values());return p
def make(p=None):return Engine.create(Compiler(providers=providers()).compile(p or package()),providers=providers(),seed=6191)
def deploy(s):s.submit({'action':'deploy','definition':'unit/peer/tank','alias':'tank','position':{'row':2,'col':3},'facing':'left'},at=0)
def ev(s,key):return [e for e in s.session.events if e['type']==key]
def test_same_actual_pointseven_counterinput_normal40_busy69_burst_fixed28():
 s=make();deploy(s);s.session.advance(1)
 cast=next(c for c in s.ctx.get('boss',('runtime','casts'),{}).values() if c['ability']==N[0]);assert cast['finish_at']==69
 assert s.ctx.get('boss',('runtime','next_attack'))==159
 s.session.advance(120)
 starts=[(e['time'],e['payload']['ability']) for e in ev(s,'ability.started')]
 burst=next(t for t,a in starts if a==B[0]);assert burst>=69
 assert any(e['time']==40 for e in ev(s,'projectile.launched'))
 assert any(e['time']==burst+28 for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss'))
 finish=next(e['time'] for e in ev(s,'ability.finished') if e['payload']['ability']==B[0]);assert finish==burst+48
def test_actual_mainattack111_pointseven_quantizes159_and_aspeed1_keeps48():
 p=package();boss=p['scenarioDraft']['initialEntities'][0];boss['components']['ability_timing']['initial_cooldowns'][B[0]]=100
 s=make(p);deploy(s);s.session.advance(161)
 assert [e['time'] for e in ev(s,'ability.started') if e['payload']['ability']==N[0]]==[0,159]
 p=package();p['scenarioDraft']['initialEntities'][0]['components']['buffs']['initial']=['buff/'+UID+'/sleepimmune']
 s=make(p);deploy(s);s.session.advance(1);cast=next(iter(s.ctx.get('boss',('runtime','casts'),{}).values()));assert cast['finish_at']==48 and s.ctx.get('boss',('runtime','next_attack'))==111
def test_real_rebirth_phase1_cold_source_burst87_full110_fixed():
 p=package();p['scenarioDraft']['initialEntities'][0]['components'].pop('ability_timing');s=make(p);deploy(s)
 s.submit({'action':'skill','source':'controller','ability':'ability/peer/hit'},at=5)
 s.submit({'action':'skill','source':'controller','ability':'ability/peer/coldboss'},at=600)
 s.session.advance(621);assert s.ctx.attributes.value('boss','attack_speed_ratio')==pytest.approx(.7)
 cast=next(c for c in s.ctx.get('boss',('runtime','casts'),{}).values() if c['ability']==B[1]);assert cast['started_at']==620 and cast['finish_at']==730
 s.session.advance(111)
 assert any(e['time']==707 and e['payload'].get('source')==s.session.world.resolve('boss') for e in ev(s,'damage.accepted'))
 assert any(e['time']==730 and e['payload']['ability']==B[1] for e in ev(s,'ability.finished'))
@pytest.mark.parametrize('tick',[39,68,70])
def test_actual_scaled_busy_public_disk_cp_and_from_head(tick,tmp_path):
 s=make();deploy(s);s.session.advance(tick);p=tmp_path/'timing.json';pin=write_ordered(p,s.checkpoint());r=Engine.restore(s.program,load_bound(p,pin),providers=providers());s.session.advance(190-tick);r.session.advance(190-tick)
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=providers()).snapshot()
