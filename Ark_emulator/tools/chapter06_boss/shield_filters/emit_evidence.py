"""Final common-core persisted capture→late CHAR kill proofs for both modules."""
from pathlib import Path
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_content_base_v1_candidate'
CORE='d81334d340034732a1840f16612073f7ae56e41a9727584ea38c74c61943439e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.tools.replay import replay
 from tools.chapter06.cold.policies import providers
 from tools.chapter06_boss.shield_filters.test_content import package,DIRS,events,COLD
 from tools.chapter06_boss.shield_filters.build_modules import ENUM,BASES
 from tools.campaign_ordered_checkpoint import write_ordered,load_bound
 from tools.campaign_streaming_evidence import observations,export_events
 audit=ROOT/'packages/campaign/chapter06_boss/shield_occupancy_audit';tests=audit/'common.filters.tests.json'
 tr=json.loads(tests.read_bytes())
 if not tr['passed'] or tr['core']!=CORE or implementation_digest()!=CORE:raise ValueError('Actualcommon core tests required')
 paths=[tests,ENUM,COLD,ROOT/'tools/chapter06/cold/policies.py',*list((ROOT/'tools/chapter06_boss/shield_filters').glob('*.py')),*[ROOT/'packages/campaign/chapter06_boss'/d/'model.json' for d in DIRS.values()]]
 before={str(p):sha(p) for p in paths};reports={}
 for which,directory in DIRS.items():
  model=ROOT/'packages/campaign/chapter06_boss'/directory/'model.json';old=ROOT/'packages/campaign/chapter06_boss'/BASES[which][0]
  m=json.loads(model.read_bytes());o=json.loads(old.read_bytes())
  for k in ['entities','abilities','rules','buffs','selectors','projectiles','behaviors']:
   if k in o:assert m[k]==o[k]
  for a,b in zip(m['definitions'],o['definitions']):
   if a.get('kind')=='ability' and 'tile_selector' in a:assert {k:v for k,v in a.items() if k not in ['tile_selector','metadata']}=={k:v for k,v in b.items() if k not in ['tile_selector','metadata']}
   else:assert a==b
  out=model.parent/'evidence';out.mkdir(exist_ok=True);p,a,t,c=package(which,dormant=True);path=out/'latechar.probe.json';write(path,p);reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,providers=reg,seed=6217);s.submit({'action':'skill','source':'controller','ability':c},at=t+1);s.session.advance(t+1)
  assert len(events(s,'tile.selection'))==1 and not s.ctx.active('victim')
  cp=out/'captured.checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg);s.session.advance(69);r.session.advance(69);rp=out/'latechar.replay.json';write(rp,s.export_replay());head=replay(program,json.loads(rp.read_bytes()),providers=reg);obs=observations(s);robs=observations(r);hobs=observations(head);assert obs==robs==hobs
  died=[e for e in events(s,'entity.died') if e['payload'].get('target')==s.session.world.resolve('victim')];assert len(died)==1 and died[0]['time']==t+55 and s.ctx.resources.current('victim','hp')==0
  reports[which]={'model_sha256':sha(model),'native_capture_start':t,'actual_death_time':died[0]['time'],'actual_hp':0,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'checkpoint':{'path':str(cp),'sha256':pin,'tick':t+1,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(out/'latechar.events.jsonl',s),'observations':obs,'checkpoint_observations':robs,'replay_observations':hobs,'checkpoint_equal':True,'replay_equal':True,'probe_scope':'Onlyunrelatedarbitration conditionsdisabled; trueShieldinitialclock/frame/count retained, inertbranchplaceholder ordinarycompile only, no fullstageclaim'}
 after={str(p):sha(p) for p in paths};assert before==after and implementation_digest()==CORE
 report={'schema':'ark-sim/ch6-shield-source-filter-author-evidence/v1','author_checks_passed':True,'core':CORE,'actual_common_test_count':14,'source_at_start':before,'source_at_completion':after,'reports':reports,'source_enum_pin':sha(ENUM),'source_policy':'CurrentnativeEXCEPT_CHARACTER2 verified; friendlyside0/CHARbit1 captureexclusion reference masks, allactualprojectedcomposites honored; laterentrant55framekill retained','independent_reviewed':False,'generic_independently_reviewed':False,'whole_stage_executed':False,'client_verified':False};p=audit/'common.author.evidence.json';write(p,report);print(json.dumps({'sha256':sha(p),'reports':{k:{'model':v['model_sha256'],'death_time':v['actual_death_time'],'checkpoint_equal':v['checkpoint_equal'],'replay_equal':v['replay_equal']} for k,v in reports.items()}}))
if __name__=='__main__':main()
