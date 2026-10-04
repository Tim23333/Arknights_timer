import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m21_integration_candidate'));sys.path.insert(1,str(ROOT))
from tools.experiments.m22_peer.verify import data,make,finish,ev,CORE
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
import UnityPy
assert implementation_digest()==CORE
results=[]
# Actual source payload and flag-to-profile checks, independent of author builder.
source=json.loads((ROOT/'packages/campaign/chapter01_sources/native.reference.json').read_bytes());npc=json.loads((ROOT/'packages/campaign/chapter01_predefines/native.reference.json').read_bytes());p,_,_=data('01-11');raw=[]
for name,record,mover in [('mocock',source['projectiles']['projectile_mocock'],'ParacurveMovement'),('crossbow',npc['projectile'],'AdvancedMovement')]:
 path=ROOT.parent/record['source']['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==record['source']['sha256'];objects={o.path_id:o for o in UnityPy.load(str(path)).objects};components={c['native_class']:objects[int(pid)].read_typetree() for pid,c in record['components'].items() if c['native_class'] in ('SimpleProjectile',mover)}
 for pid,c in record['components'].items():
  if c['native_class'] in components:assert components[c['native_class']]==c['raw']
 simple=components['SimpleProjectile'];move=components[mover];definition=next(d for d in p['projectiles'] if d['id']=='projectile/chapter01/'+name)
 assert definition['motion']['parameters']['speed']==move['_speed'] and definition['lifetime_seconds']==simple['_lifeTime'] and definition['max_hits']==simple['_maxHitNum']==1 and definition['can_hit_same_target'] is False and definition['stop_after_max'] is True and definition['lifecycle']['source_invalid']=='retain' and definition['lifecycle']['hit_on_expire'] is True
 assert simple['_canHitSameTargetMultipleTimes']==0 and simple['_stopWhenSourceInvalid']==0 and simple['_alwaysHitTraceTargetInTheEnd']==1
 raw.append({'projectile':name,'source':record['source'],'actual_components':components,'profile_exact_speed_life_quota_invalid_flags':True})
# The frame22 packet launches before target reaches its real hidden checkpoint.
p,_,aid=data('01-12');target=next(e for e in p['entities'] if e['id']=='unit/target');target['components']['attributes']['base']['move_speed']=1

p['scenarioDraft']['initialEntities'][1]['route']={'motionMode':'WALK','endPosition':{'row':3,'col':7},'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},'checkpoints':[{'type':'MOVE','position':{'row':3,'col':5.1}},{'type':'DISAPPEAR'},{'type':'WAIT_FOR_SECONDS','time':2},{'type':'APPEAR_AT_POS','position':{'row':3,'col':5.1}}]}
s=make(p);s.advance(36);assert s.ctx.route_hidden('target');assert ev(s,'projectile.launched') and any(e['payload']['reason']=='target_hidden' for e in ev(s,'projectile.invalid'));assert not [e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];results.append(finish(s,'hidden_capture_rejected',p,{'source_trace_only':True}))
# Both genuine source lifetime values actually terminate a chase outside initial range.
for level,npc_,expiry in [('01-11',False,322),('01-11',True,159)]:
 p,_,aid=data(level,npc_);p['scenarioDraft']['map']['cols']=100;next(a for a in p['abilities'] if a['id']=='ability/move')['activation']['on_start'][0]['position']['col']=90;s=make(p);s.submit({'action':'skill','source':'target','ability':'ability/move'},at=10 if npc_ else 23);s.advance(expiry+1)
 hits=[e for e in ev(s,'damage.accepted') if e['payload'].get('ability')==aid];assert len(hits)==1 and hits[0]['time']==expiry;assert ev(s,'projectile.invalid')[0]['payload']['reason']=='expired';assert len(ev(s,'projectile.hit'))==1;results.append(finish(s,'expiry_'+('crossbow' if npc_ else 'mocock'),p,{'expiry':expiry,'single_quota':True,'force_end_captured_target':True}))
# Exact kind/contract refs: never accept a callback trajectory bound as resource math.
negative=[]
for change in ('wrong_projectile_kind','wrong_trajectory_contract','legacy_speed_reintroduced'):
 p,_,aid=data('01-11');ability=next(a for a in p['abilities'] if a['id']==aid)
 if change=='wrong_projectile_kind':ability['timeline'][0]['effect']['projectile_definition']='unit/enemy_1028_mocock'
 elif change=='wrong_trajectory_contract':next(d for d in p['projectiles'] if d['id']=='projectile/chapter01/mocock')['motion']['rule']='rule/support_time_sp'
 else:
  # Existing author conversion promises absence: this is a source guard, not a core ban on legacy users.
  assert 'projectile_speed' not in ability['parameters'];negative.append({'case':change,'source_guard_passed':True});continue
 try:Compiler().compile(p)
 except ValueError as e:negative.append({'case':change,'rejected':True,'error':str(e)})
 else:raise AssertionError(change)
assert implementation_digest()==CORE
report={'schema':'ark-sim/m22-independent-boundary-review/v1','passed':True,'implementation_sha256':CORE,'raw_actual_component_sources':raw,'cases':results,'negative_cases':negative,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'result':'passed'}],'formal_approval':False,'native_method_body_and_3D_calibration':False}
out=ROOT/'validation/campaign/m22_peer/boundaries.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'runtime_cases':len(results),'raw_projectiles':len(raw),'negative_guards':len(negative)}))
