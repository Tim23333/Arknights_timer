"""Persist only actually supported Patriot mechanisms, never full-enemy gate."""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate'
CORE='d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter07_boss.test_mechanism_v5 import package,deploy,kill,ev
 from tools.chapter07_boss.build_mechanism_v1 import OUT
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 assert implementation_digest()==CORE
 reports=[OUT/'phase0.v4.tests.json',OUT/'rebirth.v5.tests.json']
 for p in reports:r=json.loads(p.read_bytes());assert r['passed'] and r['core']==CORE
 paths=[OUT/'mechanism.v3.json',OUT/'source.closure.json',*reports,*list((ROOT/'tools/chapter07_boss').glob('*.py'))];before={str(p):sha(p) for p in paths};out=OUT/'mechanism_evidence_v1';out.mkdir(exist_ok=True);actual={}
 for name,tick,end,down in [('fourhit',20,40,False),('waiting_rebirth',6,1807,True)]:
  folder=out/name;folder.mkdir(exist_ok=True);path=folder/'probe.json';write(path,package());program=Compiler().compile(path);s=Engine.create(program,seed=7187);deploy(s)
  if down:kill(s,5)
  s.session.advance(tick);cp=folder/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.session.advance(end-tick);r.session.advance(end-tick);rp=folder/'replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()));obs=observations(s);robs=observations(r);hobs=observations(head);assert obs==robs==hobs
  packets=[(e['time'],e['payload']['amount']) for e in ev(s,'damage.accepted') if e['payload'].get('source')==s.session.world.resolve('boss')]
  if down:assert s.ctx.resources.current('boss','hp')==45000*.8500000238418579 and [e['time'] for e in ev(s,'entity.rebirth.completed')]==[1805]
  else:assert packets==[(19,2620),(22,2620),(25,2620),(28,2620)]
  actual[name]={'program':program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint':{'path':str(cp),'sha256':pin,'tick':tick,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(folder/'events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True,'damage_packets':packets,'boss_hp':s.ctx.resources.current('boss','hp'),'rebirth_finishes':[e['time'] for e in ev(s,'entity.rebirth.completed')]}
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch7-patrt-partial-mechanism-author-evidence/v1','partial_checks_passed':True,'core':CORE,'model_sha256':sha(OUT/'mechanism.v3.json'),'source_closure_sha256':sha(OUT/'source.closure.json'),'source_at_start':before,'source_at_completion':after,'actual_supported_cases':5,'actual':actual,'scope':'Singleemitter quarantinedprobe. Realfourhit/blockedonly/nativeprofile/60seconds/85percent/15invul/CP/head. Sharedmarker production/multisource/HP0waitingAura/Immo/spear/ore-mine/waverelease unclosed; no nativefull-enemy equivalence claim','stage_export_allowed':False,'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False};path=out/'author.evidence.json';write(path,report);print(json.dumps({'sha256':sha(path),'model_sha256':report['model_sha256'],'actual_supported_cases':5,'checkpoint_equal':True,'replay_equal':True}))
if __name__=='__main__':main()
