import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_terminal_lifecycle_v3_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_terminal_lifecycle.test_terminal_source_v5 import package,providers
OUT=ROOT/'validation/campaign/chapter08_terminal_retained_projectile_v4'
def test_three_actual_flight_packets_after_HP0_terminal_dead_CP1145_head():
 p=package();loop=next(a for a in p['abilities'] if a['id']=='ability/terminal/screen10')
 for x in loop['timeline']:x['at_seconds']=27.7;x.pop('repeat')
 reg=providers();pr=Compiler(providers=reg).compile(p);s=Engine.create(pr,providers=reg,seed=817);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=1);s.submit({'action':'skill','source':'player','ability':'ability/counter/kill'},at=160);s.advance(1145);assert len([e for e in s.session.events if e['type']=='projectile.launched'])==3 and s.ctx.alive('boss');OUT.mkdir(parents=True,exist_ok=True);f=OUT/'flight1145.json';h=write_ordered(f,s.checkpoint());r=Engine.restore(pr,load_bound(f,h),providers=reg);s.advance(55);r.advance(55);assert s.checkpoint()==r.checkpoint()==replay(pr,s.export_replay(),providers=reg).checkpoint();hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==3 and all(e['time']>1150 and e['payload']['amount']==462 for e in hits);assert not s.ctx.alive('boss');assert s.ctx.attributes.values(s.session.world.resolve('boss'))['atk']==770;(OUT/'source.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2),encoding='utf8')
