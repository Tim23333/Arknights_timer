"""Actual source max1000 clamp, not an impractical30500s fake-long proof."""
from pathlib import Path
import hashlib,json
from tools.chapter08_special.review_dynamic_burn_v4 import ROOT,MODULE,CORE,OUT,package,registry,domain
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p,timer,child,aid=package(1001);reg=registry();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=8026);s.submit({'action':'skill','source':'source','ability':aid},at=0);folder=OUT/'source_max1000';folder.mkdir(exist_ok=True);s.session.advance(31);cp=folder/'checkpoint31.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg);s.session.advance(34);r.session.advance(34);h=replay(s.program,s.export_replay(),providers=reg);assert domain(s)==domain(r)==domain(h) and tuple(s.session.events)==tuple(r.session.events)==tuple(h.session.events)
 instance=next(i for i in s.ctx.get('target',('buffs','instances')) if i['definition']==timer);clock=thaw(instance['lifetime_clock']);assert clock['rate']==.001 and abs(clock['remaining_seconds']-(30.5-65/30000))<1e-9
 hits=[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted'];assert hits==[(30,56),(60,62)]
 result={'status':'passed_short_actual_native_max_clamp','core':implementation_digest(),'module_sha256':sha(MODULE),'input_multiplier':1001,'native_maximum_multiplier':1000,'actual_rate':clock['rate'],'clock_after65':clock,'source_D_unshortened':30.5,'independent_child_world_clock_packets':hits,'CP31_to65':True,'head_equal':True,'full_events_equal':True,'not_claimed_long_expiry':30500,'scope':'Real sampled rate/remaining decrement plus fixed child frequency; full30500s duration not executed.'};(folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode());out=folder/'report.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out)}))
if __name__=='__main__':main()
