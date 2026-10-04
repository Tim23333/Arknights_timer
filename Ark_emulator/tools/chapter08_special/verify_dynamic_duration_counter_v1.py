"""Actual initial-only v3 counter with a midlife public resistance change and exact full CP/head."""
import json,hashlib
from pathlib import Path
from tools.chapter08_special.review_dragon_fire_v2 import package,new_registry,domain,ROOT,BASE
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=ROOT/'packages/campaign/chapter08_consumers/special/dragon_fire_dynamic_source_v1';out.mkdir(exist_ok=True);module=BASE/'dragon_fire.module.v3.json';before=sha(module);p,timer,child,aid=package(3)
 buff='buff/peer/ch8/resistance_half';skill='ability/peer/ch8/resistance_half';p['buffs'].append({'id':buff,'kind':'buff','modifiers':[{'attribute':'one_minus_status_resistance','layer':'final_ratio','value':-.5}]});p['entities'][0]['components']['abilities'].append(skill);p['abilities'].append({'id':skill,'kind':'ability','selector':'selector/peer/ch8/fire/target','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'apply_buff','buff':buff}}]})
 reg=new_registry();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=8026);s.submit({'action':'skill','source':'source','ability':aid},at=0);s.submit({'action':'skill','source':'source','ability':skill},at=300)
 s.session.advance(301);cp=out/'after_change301.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg);s.session.advance(639);r.session.advance(639);head=replay(s.program,s.export_replay(),providers=reg);assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert hits[-1]['time']==900 and len(hits)==30
 expected=(10+(30.5-10)*.5)*30
 result={'status':'required_dynamic_source_gap_confirmed','runtime':implementation_digest(),'source_module':str(module),'source_before':before,'source_after':sha(module),'public_commands':s.export_replay()['commands'],'cp301_to940_equal':True,'head_equal':True,'full_events_equal':True,'actual_packets':[(e['time'],e['payload']['amount']) for e in hits],'actual_last_tick':900,'actual_parent_nominal_expiry':915,'dynamic_reference_policy_expected_expiry_seconds':20.25,'expected_quantum_ceiling_tick':608,'unrounded_frame':expected,'expected_last_world1s_packet_tick':600,'counter_scope':'Initial m1 apply; at10s actual finalratio-.5 Buff changes current Attribute26 to.5. Existing init-only timer does not shorten; original source child1s clock stays fixed. Correct dynamic lifetime consumes native remaining at current rate on each elapsed interval.','new_kernel_source_requirement':'Root-owned generic duration clock, no ID-specific branch/no changes to frozen module/runtime. First boundary consumption atnow+1; previous-interval sample plus change settle must avoid retroactive application.','client_verified':False}
 assert result['source_before']==result['source_after'];(out/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(out/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
 with (out/'events.jsonl').open('wb') as f:
  for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False,separators=(',',':'))+'\n').encode())
 result['pins']={str(f):sha(f) for f in out.iterdir() if f.is_file()};file=out/'report.json';assert not file.exists();file.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(file),'sha256':sha(file)}))
if __name__=='__main__':main()
