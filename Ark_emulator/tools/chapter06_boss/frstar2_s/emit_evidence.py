"""Persist actual full-source blood/skills CP and head with immutable guards."""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_buff_no_source_v1_candidate'
CORE='bd98da8b7f15fba7fb795bbecebd7563323f663d207561c5ae4365c760abf9fc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter06_boss.frstar2_s.test_module import package,deploy,events
 from tools.chapter06_boss.frstar2_s.test_blood import packets
 from tools.chapter06_boss.frstar2_s.build_module import OUT,COLD,UID,B,I
 from tools.chapter06.cold.policies import providers
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 if implementation_digest()!=CORE:raise ValueError('Exact candidate core required')
 paths=[OUT/'model.json',OUT/'source.closure.json',OUT/'consumption.plan.json',COLD,*list((ROOT/'tools/chapter06_boss/frstar2_s').glob('*.py'))]
 before={str(p):sha(p) for p in paths};out=OUT/'evidence';out.mkdir(exist_ok=True)
 path=out/'fullsource.probe.json';write(path,package());reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6217,providers=reg);deploy(s);s.session.advance(500)
 if s.ctx.resources.current('boss','hp')!=63000:raise ValueError('Actual16 ticks2000 must precede CP')
 cp=out/'blood500.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(950);r.session.advance(950)
 rp=out/'fullsource.replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()),providers=reg)
 obs=observations(s);robs=observations(r);hobs=observations(head)
 ps=packets(s);starts=[(e['time'],e['payload']['ability']) for e in events(s,'ability.started') if e['payload']['source']==s.session.world.resolve('boss')]
 if obs!=robs or obs!=hobs or [e['time'] for e in ps]!=list(range(30,1441,30)) or not all(e['payload']['settlement_amount']==2000 for e in ps):raise ValueError('Actual48 source timer/CP/head differs')
 if s.ctx.resources.current('boss','hp')!=0 or s.ctx.alive('boss') or len(events(s,'entity.died'))!=1 or events(s,'entity.rebirth.started') or starts!=[(480,B),(690,I)]:raise ValueError('Distinct story profile/skills/death differs')
 after={str(p):sha(p) for p in paths}
 if before!=after or implementation_digest()!=CORE:raise ValueError('Actual bound source/model/core changed')
 report={'schema':'ark-sim/ch6-frstar2-story-author-evidence/v1','author_checks_passed':True,'core':CORE,'model_sha256':sha(OUT/'model.json'),'source_sha256':sha(OUT/'source.closure.json'),'source_at_start':before,'source_at_completion':after,'actual':{'first_tick':30,'ticks':[e['time'] for e in ps],'request_amount':2000,'last_actual_health_loss':ps[-1]['payload']['actual_health_loss'],'final_hp':0,'died_events':1,'rebirth_events':0,'skill_starts':starts,'no_normal_projectiles':not events(s,'projectile.launched'),'source_policy':'none','attack_type':'BUFF','ignore_for_sp':True,'damage_without_modify':True},'program':program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint':{'path':str(cp),'sha256':pin,'tick':500,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(out/'fullsource.events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True,'test_history':'5 pre-gap source/skill+CP and5 control cases passed a705; oldblood v1 batch5passed3fixturefailed, then only3 correctedpassed;2full-source coexist cases passedbd98. Do not relabel failed batch overall pass. Finalbound fullmodel CP500/head persisted here.','generic_independently_reviewed':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
 p=out/'author.evidence.json';write(p,report);print(json.dumps({'report_sha256':sha(p),'checkpoint_equal':True,'replay_equal':True,'model_sha256':report['model_sha256']}))
if __name__=='__main__':main()
