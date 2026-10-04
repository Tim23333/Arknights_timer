"""Fresh independent current-stage no-marker and validation-witness native filter gate."""
import hashlib,json,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_behavior_restart_clock_v2_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter08_stage_join.runner_providers_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'packages/campaign/chapter08_consumers/special/uoffcr_marker_gate_v2';MODULE=ROOT/'packages/campaign/chapter08_consumers/ranged/uoffcr.module.v3.json';MARKER='buff/ch8/source/mark_neutral[effect]'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def domain(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'rng':s.session.random.snapshot(),'time':s.session.time}
def make_case(blocked=False,marked=False,camo=False,air=False,free=False):
 p=json.loads(MODULE.read_bytes());uid=p['entities'][0]['id'];target='unit/peer/ch8/uoffcr/target';skill='ability/peer/ch8/uoffcr/mark';p['entities'].append({'id':target,'kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':137,'mres':31,'block_count':1 if blocked else 0,'taunt_level':1000000000}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':2 if air else 1,'category':1,'unit_type':1,'camouflage':camo,'target_free':free},'spatial':{},'deployable':{'base_cost':3,'capacity':1,'cooldown_seconds':0,'terrain':'ground','refund_ratio':0},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':[skill]}});p['abilities'].append({'id':skill,'kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':0,'effect':{'op':'apply_buff','target':'source','buff':MARKER}}]});p['scenarioDraft']={'id':'scene/peer/uoffcr/marker_gate','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':5},'objectives':{},'resources':{'dp':{'initial':20,'capacity':99}},'initialEntities':[{'definition':uid,'instanceAlias':'source','position':{'row':1,'col':0},'route':{'motionMode':'WALK','startPosition':{'row':1,'col':0},'endPosition':{'row':1,'col':4},'checkpoints':[]}}]}
 if blocked:p['scenarioDraft']['roster']=[target]
 else:p['scenarioDraft']['initialEntities'].append({'definition':target,'instanceAlias':'target','position':{'row':1,'col':1}})
 p['manifest']['metadata']['peer_fixture']='Positive marker is a validation witness only, not a native NPC production or stage predefine.'
 s=Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=8107)
 if blocked:s.submit({'action':'deploy','entity':target,'row':1,'col':0,'alias':'target'},at=0)
 if marked:s.submit({'action':'skill','source':'target','ability':skill},at=0)
 return s,p
def run(name,kwargs,end=45):
 s,p=make_case(**kwargs);folder=OUT/name;folder.mkdir(exist_ok=True);s.session.advance(10);cp=folder/'checkpoint.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h),providers=providers());s.session.advance(end-10);r.session.advance(end-10);head=replay(s.program,s.export_replay(),providers=providers());assert domain(s)==domain(r)==domain(head) and tuple(s.session.events)==tuple(r.session.events)==tuple(head.session.events)
 shots=[e for e in s.session.events if e['type']=='projectile.launched'];hits=[e for e in s.session.events if e['type']=='damage.accepted'];row={'name':name,'parameters':kwargs,'cp_equal':True,'head_equal':True,'events_equal':True,'shots':[(e['time'],e['payload']['target']) for e in shots],'damage':[(e['time'],e['payload']['amount']) for e in hits],'hp':s.ctx.resources.current('target','hp'),'DP':s.ctx.resources.current('system/battle','dp')}
 (folder/'input.json').write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());(folder/'replay.json').write_bytes((json.dumps(s.export_replay(),ensure_ascii=False,indent=2)+'\n').encode())
 with (folder/'events.jsonl').open('wb') as f:
  for e in s.session.events:f.write((json.dumps(thaw(e),ensure_ascii=False,separators=(',',':'))+'\n').encode())
 row['pins']={str(q):sha(q) for q in folder.iterdir() if q.is_file()};return row
def main():
 draft=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.json';overlay=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v3.life99999.v1.json';assert sha(draft)=='8a5debd1963964e9a3f59aa19cd91625ebe9f7108676016151c2030c98786efa';assert sha(overlay)=='f48318f619e63e391d7ee40b111becb1a40c54e14db432923d4d72664d88505f';OUT.mkdir(exist_ok=True);before=sha(MODULE);rows=[];a=run('unblocked_ordinary_no_marker',{});assert not a['shots'] and not a['damage'];rows.append(a)
 a=run('blocked_ordinary_no_marker',{'blocked':True});assert not a['shots'] and a['damage']==[(16,193)] and a['DP']==17;rows.append(a)
 a=run('marked_witness',{'marked':True});assert len(a['shots'])==1 and len(a['damage'])==1 and a['damage'][0][1]==193;rows.append(a)
 for name,kwargs in [('marked_camo',{'marked':True,'camo':True}),('marked_air',{'marked':True,'air':True}),('marked_target_free',{'marked':True,'free':True})]:
  a=run(name,kwargs);assert not a['shots'] and not a['damage'];rows.append(a)
 assert before==sha(MODULE);roster=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';p=json.loads(roster.read_bytes());definitions=p.get('definitions',[]);markproduction=[d['id'] for d in definitions if MARKER in json.dumps(d,ensure_ascii=False)];assert not markproduction
 result={'status':'passed_declared_marker_filter_stage_scope','core':implementation_digest(),'source_module_sha256':before,'source_after':sha(MODULE),'source_audit_sha256':sha(OUT.parent/'uoffcr_marker_gate_v1/source.audit.json'),'actual_cases':rows,'current_draft_identity':{'native':sha(draft),'life_overlay':sha(overlay),'runner_providers':sha(ROOT/'tools/chapter08_stage_join/runner_providers_v1.py')},'current_fixed12_roster':{'path':str(roster),'sha256':sha(roster),'marker_refs_or_producers':markproduction},'interpretation':'Native positive marker include condition supported by fixed DB explicit remote-only-NPC description, ConditionFilter/_CheckBuff declarations and current reference. Full native method body not recovered; exact check ordering remains replaceable. Current JT8-2 producer scope has no marked NPC, so no ranged fallback is intentional. Combat tests use real public ordinary deployment and no marker.','positive_witness_not_complete_NPC':True,'whole_stage_executed':False,'client_verified':False};out=OUT/'gate.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'cases':len(rows)}))
if __name__=='__main__':main()
