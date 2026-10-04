"""Actual waiting HP0 Immo and public replay on frozen waiting-action core."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_waiting_actions_v1_candidate'
CORE='4dc5c3c7a4c2a2fccc1d6bb8cee63a0a5e86df16fa644e17fc2a91cbdc6c67fa'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter07_boss.test_waiting_v2 import package,deploy,kill,ev
 from tools.chapter07_boss.build_mechanism_v1 import OUT
 from tools.chapter07_boss.build_waiting_v1 import IMMO
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 assert implementation_digest()==CORE;r=json.loads((OUT/'waiting.v2.tests.json').read_bytes());assert r['passed'] and r['core']==CORE
 paths=[OUT/'source.closure.json',OUT/'waiting.mechanism.v2.json',OUT/'waiting.v2.tests.json',ROOT/'tools/chapter07_boss/test_waiting_v2.py',ROOT/'tools/chapter07_boss/build_waiting_v1.py',ROOT/'tools/chapter07_boss/build_waiting_v2.py',Path(__file__)];before={str(p):sha(p) for p in paths};out=OUT/'waiting_evidence_v1';out.mkdir(exist_ok=True);path=out/'probe.json';write(path,package());program=Compiler().compile(path);s=Engine.create(program,seed=7187);deploy(s);kill(s,5);s.session.advance(6);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss')
 cp=out/'hp0.checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin));s.session.advance(49);restored.session.advance(49);rp=out/'replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()));obs=observations(s);robs=observations(restored);hobs=observations(head);assert obs==robs==hobs
 starts=[e['time'] for e in ev(s,'ability.started') if e['payload']['ability']==IMMO];packets=[(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')];assert starts==[29,53] and len(packets)==2 and all(abs(x[1]-1920*.0521)<1e-6 for x in packets);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch7-patrt-waiting-action-author-evidence/v1','author_checks_passed':True,'actual_cases':7,'core':CORE,'model_sha256':sha(OUT/'waiting.mechanism.v2.json'),'source_at_start':before,'source_at_completion':after,'actual':{'hp':0,'active':False,'alive':True,'action_starts':starts,'packets':packets,'current_source_atk':1920,'globalAura_continuity_unclosed_expected_fullatk':2240},'program':program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint':{'path':str(cp),'sha256':pin,'tick':6,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(out/'events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True,'stage_export_allowed':False,'complete_source_policies':False,'source_health_granted':False,'projectile_permission_borrowed':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False};p=out/'author.evidence.json';write(p,report);print(json.dumps({'sha256':sha(p),'actual':report['actual']}))
if __name__=='__main__':main()
