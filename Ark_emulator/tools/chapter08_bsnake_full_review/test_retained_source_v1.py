"""Separate declared public defeat after native launch; not the 140-ray run."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_bsnake_combat.policies_v1 import providers as combat
from tools.chapter08_bsnake_skills.policies_v1 import providers as skills
from tools.chapter08_bsnake.screen_policy_v1 import providers as screen
from tools.chapter08_joint_v4.build_summon_hint_v2 import providers as hint
from tools.chapter08_flame_device.policies_v1 import providers as flame
def providers():return {**combat(),**skills(),**screen(),**hint(),**flame()}
def run():
 out=ROOT/'validation/campaign/chapter08_bsnake_retained_source_v1';out.mkdir(exist_ok=False)
 p=json.loads((ROOT/'validation/campaign/chapter08_bsnake_full_input_v2/input.json').read_bytes())
 for d in p['definitions']:
  if d['id']=='unit/peer/source_director':d['components']['abilities'].append('ability/peer/terminal_defeat')
 p['definitions'].append({'id':'ability/peer/terminal_defeat','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'instant_kill','target':20,'parameters':{'cause':'peer_retained_public_source','skip_rebirth':True}}]},'timeline':[]})
 p['manifest']['id']='package/peer/bsnake_native_retained_short'
 commands=[{'action':'skill','source':'director','ability':'ability/peer/defeat','at':57},{'action':'skill','source':'director','ability':'ability/peer/terminal_defeat','at':268}]
 for name,x in [('input.json',p),('commands.json',commands)]:
  (out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
 program=Compiler(providers=providers()).compile(p);s=Engine.create(program,providers=providers(),seed=884500)
 for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
 s.advance(268);pin=write_ordered(out/'pre_retire268.json',s.checkpoint());r=Engine.restore(program,load_bound(out/'pre_retire268.json',pin),providers=providers())
 s.advance(92);r.advance(92);h=replay(program,s.export_replay(),providers=providers())
 assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 hits=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload']['ability']=='ability/ch8/bsnake/firecommon']
 assert len(hits)==7
 for ref,res in zip(range(13,20),[17,37,53,73,17,37,53]):
  found=[e for e in hits if e['payload']['target']==ref];assert len(found)==1
  assert found[0]['time']>268 and abs(found[0]['payload']['amount']-770*(1-res/100))<1e-9
 for name,sim in [('forward',s),('restored',r),('head',h)]:
  (out/(name+'.json')).write_text(json.dumps({'checkpoint':sim.checkpoint(),'events':thaw(tuple(sim.session.events)),'replay':sim.export_replay()},ensure_ascii=False,separators=(',',':')),encoding='utf8')
 report={'passed':True,'core':implementation_digest(),'scope':'Separate source-native launch then declared public skipRebirthTrue defeat/currentATK after cleanup; not140 natural screen, notwhole.','actual_hits':hits,'ordered_cp_and_public_head_equal':True,'cp_sha':pin}
 (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print(hashlib.sha256((out/'verification.json').read_bytes()).hexdigest())
if __name__=='__main__':run()
