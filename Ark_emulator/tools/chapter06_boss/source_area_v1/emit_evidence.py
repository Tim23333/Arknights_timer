"""Final multi-target source-area proofs, persisted on exact common v2 core."""
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
 from tools.chapter06.cold.policies import providers
 from tools.chapter06_boss.source_area_v1.build_modules import BASES
 from tools.chapter06_boss.source_area_v1.test_area import package,CASES,COLD,ev,check
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 out=ROOT/'packages/campaign/chapter06_boss/source_area_v1';reports=[out/'area.tests.json',out/'gate.tests.json']
 for p in reports:
  r=json.loads(p.read_bytes());assert r['passed'] and r['core']==CORE
 assert implementation_digest()==CORE
 paths=[*reports,out/'c4.static.audit.json',COLD,*list((ROOT/'tools/chapter06_boss/source_area_v1').glob('*.py')),*[ROOT/'packages/campaign/chapter06_boss'/x[2]/'model.json' for x in BASES.values()]];before={str(p):sha(p) for p in paths}
 delta={}
 for which,(old,pin,new) in BASES.items():
  oldp=ROOT/'packages/campaign/chapter06_boss'/old/'model.json';newp=ROOT/'packages/campaign/chapter06_boss'/new/'model.json';assert sha(oldp)==pin;o=json.loads(oldp.read_bytes());m=json.loads(newp.read_bytes())
  for bucket in ['entities','rules','buffs','selectors','projectiles','behaviors','definitions']:
   if bucket in o:assert o[bucket]==m[bucket]
  for a,b in zip(m['abilities'],o['abilities']):
   for entry in a.get('timeline',[]):
    e=entry.get('effect',{})
    if e.get('op')=='area' and e.get('center')=='source':assert e.pop('target')=='source'
   assert a==b
  delta[which]='Onlysource-centredarea targetsource andmanifestprovenance changed; selector/gate/payload/duration/otherdefinitions invariant'
 actual={}
 for case in CASES:
  p,b,t,f,d=package(case);folder=out/case;folder.mkdir(exist_ok=True);path=folder/'probe.json';write(path,p);reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,providers=reg,seed=6219)
  if case=='ordinary1':s.submit({'action':'skill','source':'controller','ability':'ability/test/area/kill'},at=5)
  s.submit({'action':'skill','source':'outer','ability':'ability/test/area/enter'},at=t+1);tick=t+10;s.session.advance(tick);cp=folder/'midcast.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(t+f+1-tick);r.session.advance(t+f+1-tick);rp=folder/'replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()),providers=reg);obs=observations(s);robs=observations(r);hobs=observations(head);assert obs==robs==hobs;check(s,b,t,f,d)
  actual[case]={'program':program.fingerprint,'runtime':s.runtime_fingerprint,'cast_start':t,'gate_targets':2,'area_count':1,'actual_members':3,'impact_tick':t+f,'damage_each':d,'cold_each':1,'unexpected_freeze':False,'checkpoint':{'path':str(cp),'sha256':pin,'tick':tick,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(folder/'events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True}
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch6-source-area-final-author-evidence/v1','author_checks_passed':True,'core':CORE,'actual_cases':11,'source_at_start':before,'source_at_completion':after,'model_deltas':delta,'actual':actual,'fixture_scope':'Unrelatedbossarbitration conditions disabled, actualBurst sourceinit/frame/clock preserved. Phase1 onlypublicHP0/realrebirth. Threeactorsaliveatcast; thirdinitiallyoutsidegate, publicmoveintoouterarea beforeimpact. SPfixture countsacceptedpackets withoutFrozenrecovery binding, notnativeNPCSPclaim.','generic_area_semantics_changed':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False};p=out/'author.evidence.json';write(p,report);print(json.dumps({'sha256':sha(p),'cases':{k:{'area_count':v['area_count'],'damage_each':v['damage_each'],'checkpoint_equal':v['checkpoint_equal'],'replay_equal':v['replay_equal']} for k,v in actual.items()}}))
if __name__=='__main__':main()
