"""Bound actual spear, effective threat/tile gates and active Immo on af16."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_target_tile_facts_v1_candidate'
CORE='af16e21678f04bcf6ab2ca64b8829da8511bb82cffea6f5c9906fba9b1bdc0da'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter07_boss.test_spear_v2 import package,make,deploy,kill,ev,test_actual_highground_mask_ignores_huge_ground_taunt_and_uses_farther_high,test_actual_hate_first_lex_not_finitepriority_constant,test_actual_alive_rage_immo_single_sourcearea_all_ground_targets_per24ticks
 from tools.chapter07_boss.build_mechanism_v1 import OUT
 from tools.chapter07_boss.build_mechanism_v4 import SPEAR
 from tools.chapter07_boss.policies_v1 import providers
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 assert implementation_digest()==CORE;r=json.loads((OUT/'spear.projectile.v3.tests.json').read_bytes());assert r['passed'] and r['core']==CORE
 paths=[OUT/'source.closure.json',OUT/'mechanism.v5.json',OUT/'spear.projectile.v3.tests.json',ROOT/'tools/chapter07_boss/policies_v1.py',ROOT/'tools/chapter07_boss/test_spear_v2.py',ROOT/'tools/chapter07_boss/build_mechanism_v4.py',ROOT/'tools/chapter07_boss/build_mechanism_v5.py',Path(__file__)];before={str(p):sha(p) for p in paths}
 test_actual_highground_mask_ignores_huge_ground_taunt_and_uses_farther_high();test_actual_hate_first_lex_not_finitepriority_constant();test_actual_alive_rage_immo_single_sourcearea_all_ground_targets_per24ticks()
 out=OUT/'spear_evidence_v1';out.mkdir(exist_ok=True);path=out/'probe.json';write(path,package());reg=providers();program=Compiler(providers=reg).compile(path);s=Engine.create(program,providers=reg,seed=7187);deploy(s);kill(s,5);s.session.advance(2307);assert [e['time'] for e in ev(s,'projectile.launched')]==[2306]
 cp=out/'inflight.checkpoint.json';pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(15);restored.session.advance(15);rp=out/'replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()),providers=reg);obs=observations(s);robs=observations(restored);hobs=observations(head);assert obs==robs==hobs
 hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('target')==s.session.world.resolve('high_far')];assert len(hits)==1 and hits[0]['time']==2321 and hits[0]['payload']['amount']==2924
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch7-patrt-spear-alive-immo-author-evidence/v1','author_checks_passed':True,'actual_cases':6,'core':CORE,'model_sha256':sha(OUT/'mechanism.v5.json'),'source_at_start':before,'source_at_completion':after,'actual':{'real_rebirth_complete':1805,'spear_start':2255,'source_init_after_rage_seconds':15,'projectile_launch':2306,'fixedexpiry_hit':2321,'damage':2924,'source_atk':2240,'atk_scale':1.35,'target_def':100,'actual_tile_gate':2,'hate_farthest_id_lex':True,'alive_immo_first_ticks':[1829,1853],'immo_each':2240*.0521},'program':program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint':{'path':str(cp),'sha256':pin,'tick':2307,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(out/'events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True,'projectile_policy':'OnlySimpleProjectile noMover/lifetime.5/endHit1 source; fixedexpiry motionreference, nativevisualpathbody unverified. Zero inventedspeed.','stage_export_allowed':False,'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False};p=out/'author.evidence.json';write(p,report);print(json.dumps({'sha256':sha(p),'model_sha256':report['model_sha256'],'checkpoint_equal':True,'replay_equal':True}))
if __name__=='__main__':main()
