"""Bound timing correction witness with actual busy-state disk CP/head."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
CORE='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter06_boss.frstar2_v2.test_timing import package,deploy,ev,INPUT
 from tools.chapter06_boss.frstar2_v2.build_module import OUT,OLD,N,B
 from tools.chapter06.cold.policies import providers
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 paths=[OUT/'model.v2.json',OUT/'timing.tests.json',INPUT,*list((ROOT/'tools/chapter06_boss/frstar2_v2').glob('*.py')),OLD/'delivery.pins.json',ROOT/'packages/campaign/chapter06_boss/frstar2_s/delivery.pins.json']
 before={str(p):sha(p) for p in paths}
 if implementation_digest()!=CORE or not json.loads((OUT/'timing.tests.json').read_bytes())['passed']:raise ValueError('Actual final tests/core required')
 old=json.loads((OLD/'delivery.pins.json').read_bytes());assert all(sha(ROOT/k)==v for k,v in old['pins'].items())
 story=ROOT/'packages/campaign/chapter06_boss/frstar2_s';sf=json.loads((story/'delivery.pins.json').read_bytes());assert all(sha(ROOT/k)==v for k,v in sf['pins'].items())
 m=json.loads((OUT/'model.v2.json').read_bytes());o=json.loads((OLD/'model.json').read_bytes())
 for bucket in ['entities','buffs','selectors','projectiles','behaviors','definitions']:assert m[bucket]==o[bucket]
 for a,b in zip(m['abilities'],o['abilities']):assert {k:v for k,v in a.items() if k!='rules'}=={k:v for k,v in b.items() if k!='rules'}
 out=OUT/'evidence';out.mkdir(exist_ok=True);p=out/'pointseven.probe.json';write(p,package());reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=6191);deploy(s);s.session.advance(68)
 cast=next(c for c in s.ctx.get('boss',('runtime','casts'),{}).values() if c['ability']==N[0]);assert cast['finish_at']==69 and s.ctx.get('boss',('runtime','next_attack'))==159
 cp=out/'busy68.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(122);r.session.advance(122);rp=out/'pointseven.replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()),providers=reg)
 obs=observations(s);robs=observations(r);hobs=observations(head);assert obs==robs==hobs
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch6-frstar2-timing-v2-author-evidence/v1','author_checks_passed':True,'core':CORE,'model_sha256':sha(OUT/'model.v2.json'),'source_at_start':before,'source_at_completion':after,'attributes_payloads_branch_rebirth_unchanged':True,'ordinary30pins_unchanged':True,'story25pins_unchanged':True,'actual':{'normal0_start':0,'normal0_launch':40,'normal0_finish':69,'first_attack_next':159,'skill_starts':[(e['time'],e['payload']['ability']) for e in ev(s,'ability.started')],'skill_finishes':[(e['time'],e['payload']['ability']) for e in ev(s,'ability.finished')]},'program':program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint':{'path':str(cp),'sha256':pin,'tick':68,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(out/'pointseven.events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True,'source_policy':'Normal nativeTimeMode0 scaleswindup+duration; Burst nativeTimeMode1 fixes28/48 and87/110; Shield fixed55/90. affectedBySlowDown interpretation reference remainsreplaceable.','independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
 p=out/'author.evidence.json';write(p,report);print(json.dumps({'sha256':sha(p),'model_sha256':report['model_sha256']}))
if __name__=='__main__':main()
