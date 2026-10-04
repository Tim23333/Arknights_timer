"""Preserve actual764 vs immutable source-contract765; no expectation lowered to make it green."""
from pathlib import Path
import json,hashlib
from tools.chapter08_special.review_dynamic_burn_v2 import package,registry,domain,ROOT,MODULE,CORE
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 folder=ROOT/'packages/campaign/chapter08_consumers/special/dynamic_reverse_required_v1';folder.mkdir(exist_ok=True);before=sha(MODULE);p,timer,child,aid=package(1);p['entities'][1]['components']['buffs']={'initial':['buff/peer/dynamic/resistance']};reg=registry();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=8026);s.submit({'action':'skill','source':'source','ability':aid},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/dynamic/remove'},at=150)
 s.session.advance(151);cp=folder/'checkpoint151.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg);s.session.advance(629);r.session.advance(629);h=replay(s.program,s.export_replay(),providers=reg);assert domain(s)==domain(r)==domain(h) and tuple(s.session.events)==tuple(r.session.events)==tuple(h.session.events)
 removed=[e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==timer];assert removed==[764]
 result={'status':'required_previous_interval_boundary_counter','runtime':implementation_digest(),'module':str(MODULE),'module_before':before,'module_after':sha(MODULE),'original_expected':765,'actual_removed':removed,'expected_calculation':'Native duration30.5: first5s atdecay2 consumes10native seconds, remaining20.5 atdecay1;5+20.5=25.5s=765ticks. Public removalat150 is applied afterexisting same-tick pulse; nextinterval must sample newrate1 rather than retain2 until151.','not_counted_as_source_pass':True,'self_consistent_CP151_to780':True,'self_consistent_head':True,'full_events_equal':True,'commands':s.export_replay()['commands'],'new_capability_owned_by_root':'End-boundary resample afterall effects fornextinterval; oldpulse uses priorrate. No source IDs/ActorIDs in kernel.'}
 assert before==sha(MODULE) and implementation_digest()==CORE;(folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
 with (folder/'events.jsonl').open('wb') as f:
  for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False,separators=(',',':'))+'\n').encode())
 result['pins']={str(q):sha(q) for q in folder.iterdir() if q.is_file()};out=folder/'report.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out)}))
if __name__=='__main__':main()
