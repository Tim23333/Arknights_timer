"""Freeze supported exact three mode consumers and persisted public CP/head."""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate'
CORE='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter07_boss.demons.test_modules_v2 import package,deploy,change,ev,packets
 from tools.chapter07_boss.demons.build_modules import OUT,NAMES
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 assert implementation_digest()==CORE;reports=[OUT/'author.v1.tests.json',OUT/'mode_transition.v2.tests.json',OUT/'boundaries.v1.tests.json',OUT/'boundary_restore.v2.tests.json']
 for p in reports:assert json.loads(p.read_bytes())['core']==CORE
 assert json.loads(reports[1].read_bytes())['passed'] and json.loads(reports[3].read_bytes())['passed']
 paths=[*reports,*list((ROOT/'tools/chapter07_boss/demons').glob('*.py')),*[OUT/(n+suffix) for n in NAMES for suffix in ['.source.json','.module.v1.json']]];before={str(p):sha(p) for p in paths};actual={}
 for name in NAMES:
  out=OUT/name;out.mkdir(exist_ok=True);path=out/'public.probe.json';write(path,package(name,outer=name!=NAMES[0]));program=Compiler().compile(path);s=Engine.create(program,seed=7178)
  if name==NAMES[0]:deploy(s)
  change(s,1,5 if name==NAMES[0] else 2);s.session.advance(15);cp=out/'mode15.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.session.advance(145);r.session.advance(145);rp=out/'replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()));obs=observations(s);robs=observations(r);hobs=observations(head);assert obs==robs==hobs
  actual[name]={'model_sha256':sha(OUT/(name+'.module.v1.json')),'source_sha256':sha(OUT/(name+'.source.json')),'program':program.fingerprint,'runtime':s.runtime_fingerprint,'mode':s.ctx.get('enemy',('behavior','state')),'packets':packets(s),'area_count':len(ev(s,'area.resolved')),'checkpoint':{'path':str(cp),'sha256':pin,'tick':15,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(out/'events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True}
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch7-demons-source-author-evidence/v1','author_checks_passed':True,'actual_cases_cumulative':20,'core':CORE,'source_at_start':before,'source_at_completion':after,'actual':actual,'test_history':'First12:10passed2schedulerphase fixturefailed, correctedonly2 passed. Boundaries8:6passed2expiredmode0clock fixturefailed, correctedonly2passed. Originalfailedbatch receipts preserved; notmarkedoverallgreen. Finalbound three CP15/headactual here.','mode_policy':'Nativeorelistener externalRootproducer separately. Sameactor mode0/mode1, transientinterrupt implementsrestartFSM; accrued mode/mainclock preserved reference. Melee hooks16/35 vs29/49 correct. Casters nativeNeverTrigger no ordinary; actualImmo init0/CD5/SP0/range1.5→2.5 instantonearea, internal.1clock notusedskillcadence.','independent_reviewed':False,'whole_stage_executed':False,'client_verified':False};p=OUT/'author.evidence.json';write(p,report);print(json.dumps({'sha256':sha(p),'actual_cases_cumulative':20,'modules':{n:v['model_sha256'] for n,v in actual.items()}}))
if __name__=='__main__':main()
