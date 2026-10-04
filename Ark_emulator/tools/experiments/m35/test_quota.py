import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m35_integrated_candidate';sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
CORE='03cff618895019aa9b9a2e8459a08bd50a482c8c48e80ca32c92a41afb54c3f3'
def reached(inputs,parameters,context):
 return {'position':thaw(inputs['positions'][0]['position']),'motion_state':{'age':inputs['trajectory_parameters']['age_seconds']},'reached':inputs['trajectory_parameters']['age_seconds']>0}
reached.version='independent-reach-at-step-one-v1'
def second_step_collision(inputs,parameters,context):
 return {'hits':[e['id'] for e in inputs['entities'] if 'secondary' in e['tags']] if context['time']>=2 else [],'stop':False,'terrain_hit':False}
second_step_collision.version='independent-collision-step-two-v1'
PROVIDERS={**BUILTIN_PROVIDERS,'peer.reach':reached,'peer.second':second_step_collision}
def fixture():
 def actor(id,tags,abilities=[]):return {'id':id,'kind':'entity','tags':tags,'components':{'spatial':{},'attributes':{'base':{'atk':40,'max_hp':200,'def':0,'mres':0}},'resources':{'hp':{'initial':200,'capacity':200,'role':'health'}},'abilities':abilities}}
 return {'entities':[actor('unit/source',['source'],['ability/fire']),actor('unit/target',['primary','player']),actor('unit/second',['secondary','player'])],
 'selectors':[{'id':'selector/primary','kind':'selector','region':{'type':'all'},'filters':[{'tag':'primary'},{'state':'alive'}],'limit':1}],
 'rules':[{'id':'rule/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'peer.reach'}},{'id':'rule/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'peer.second'}}],
 'abilities':[{'id':'ability/fire','kind':'ability','selector':'selector/primary','activation':{'mode':'manual'},'parameters':{'wait_for_projectiles':True},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true','projectile_definition':'projectile/probe'}}]}],
 'projectiles':[{'id':'projectile/probe','kind':'projectile','motion':{'rule':'rule/motion'},'collision':{'rule':'rule/collision','allow_other_targets':True},'lifetime_seconds':.1,'max_hits':None,'can_hit_same_target':True,'stop_after_max':True,'stop_after_first':True,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':False,'hit_on_reach':True,'force_reach_on_expire':False,'hit_on_expire':True},'on_invalid':[]}],
 'scenarioDraft':{'id':'scenario/independent_unlimited','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'objectives':{},'initialEntities':[{'definition':'unit/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/target','instanceAlias':'a','position':{'row':0,'col':1}},{'definition':'unit/second','instanceAlias':'b','position':{'row':0,'col':2}}]}}
def make(p=None):
 assert (CORE is None or implementation_digest()==CORE) and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';s=Engine.create(Compiler(providers=PROVIDERS).compile(p or fixture()),seed=2802,providers=PROVIDERS);s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=0);return s
def events(s,name):return [e for e in s.session.events if e['type']==name]
def test_stop_first_reach_hit_must_finish_before_future_collision_or_expiry():
 s=make();s.advance(4);assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted')]==[(1,40)];assert s.ctx.resources.current('a','hp')==160 and s.ctx.resources.current('b','hp')==200;assert [e['time'] for e in events(s,'ability.finished')]==[1]

def check_replay(s):
 r=Engine.restore(s.program,s.checkpoint(),providers=PROVIDERS);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=PROVIDERS).snapshot()
@pytest.mark.parametrize('cap',[None,2,1])
def test_first_reach_immediate_finish_finite_and_infinite(cap):
 p=fixture();p['projectiles'][0]['max_hits']=cap;s=make(p);s.advance(2);assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted')]==[(1,40)];assert [e['time'] for e in events(s,'projectile.invalid')]==[1];assert not [t for t in s.session.scheduler.pending if t['kind'].startswith('domain.projectile.')];assert s.ctx.projectiles._inflight_hits=={};check_replay(s)
def test_expiry_dispatch_one_packet_and_deadline_reason():
 p=fixture();p['projectiles'][0]['lifetime_seconds']=0;p['projectiles'][0]['lifecycle']['hit_on_reach']=False;s=make(p);s.advance(1);assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted')]==[(0,40)];assert [(e['time'],e['payload']['reason']) for e in events(s,'projectile.invalid')]==[(0,'expired')];check_replay(s)
def test_no_stopfirst_unlimited_reach_collision_and_expiry_repeat():
 p=fixture();p['projectiles'][0]['stop_after_first']=False;s=make(p);s.advance(4);assert [(e['time'],e['payload']['target']) for e in events(s,'damage.accepted')]==[(1,3),(2,4),(2,3),(3,3)];assert s.ctx.resources.current('a','hp')==80 and s.ctx.resources.current('b','hp')==160;check_replay(s)
def test_no_repeat_targets_still_allow_other_target_before_expiry():
 p=fixture();p['projectiles'][0].update(stop_after_first=False,can_hit_same_target=False);s=make(p);s.advance(4);assert [(e['time'],e['payload']['target']) for e in events(s,'damage.accepted')]==[(1,3),(2,4)];check_replay(s)
def test_invalid_reach_target_does_not_consume_first_valid_quota():
 p=fixture();p['entities'][1]['components']['abilities']=['ability/retire'];p['abilities'].append({'id':'ability/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]});s=make(p);s.submit({'action':'skill','source':'a','ability':'ability/retire'},at=1);s.advance(4);assert [(e['time'],e['payload']['target']) for e in events(s,'damage.accepted')]==[(2,4)];assert s.ctx.resources.current('a','hp')==200 and s.ctx.resources.current('b','hp')==160;check_replay(s)
@pytest.mark.parametrize('policy,expected',[('retain',[(1,40)]),('cancel',[])])
def test_source_retire_flag_is_preserved(policy,expected):
 p=fixture();p['projectiles'][0]['lifecycle']['source_invalid']=policy
 p['entities'].append({'id':'unit/director','kind':'entity','components':{'spatial':{},'abilities':['ability/retire_source']}});p['selectors'].append({'id':'selector/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'source'}],'limit':1});p['abilities'].append({'id':'ability/retire_source','kind':'ability','selector':'selector/source','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdraw'}}]},'timeline':[]});p['scenarioDraft']['initialEntities'].append({'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':3}});s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/retire_source'},at=1);s.advance(4);assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted')]==expected;check_replay(s)
def test_callback_failure_rolls_back_quota_and_reservation():
 p=fixture();p['rules'].append({'id':'rule/fail','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}});p['projectiles'][0]['on_invalid']=[{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','target':'source','resource':'hp','amount':-1}]},{'op':'modify_resource','target':'source','resource':'hp','amount_rule':'rule/fail'}];s=make(p);s.advance(1);before=s.checkpoint()
 with pytest.raises(Exception):s.ctx.projectiles.step(s.session,{'projectile':'projectile/1'})
 assert s.checkpoint()==before and s.ctx.projectiles._inflight_hits=={}

def test_same_id_reentrant_hit_reservation_protects_first_quota():
 s=make();original=s.ctx.effects.execute;observed=[]
 def execute(source,targets,effect,ability=None,cast=None,cause=None):
  if (cast or {}).get('projectile_impact') and effect['op']=='damage':
   x=s.ctx.projectiles._get('projectile/1');observed.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/probe'],s.session.world.resolve('b')))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=execute;s.advance(3);assert observed==[False];assert [(e['time'],e['payload']['target']) for e in events(s,'damage.accepted')]==[(1,3)];assert s.ctx.projectiles._inflight_hits=={};assert s.ctx.resources.current('b','hp')==200
 # This is actual API reentrancy instrumentation, not a replayed public command.
def test_reentrant_finish_during_packet_never_reinserts_active_or_reschedules():
 s=make();original=s.ctx.effects.execute;finished=[]
 def execute(source,targets,effect,ability=None,cast=None,cause=None):
  result=original(source,targets,effect,ability,cast,cause)
  if (cast or {}).get('projectile_impact') and effect['op']=='damage':
   x=s.ctx.projectiles._get('projectile/1');s.ctx.projectiles._finish(x,'external_finish');finished.append(True)
  return result
 s.ctx.effects.execute=execute;s.advance(4);assert finished==[True];x=s.ctx.projectiles._get('projectile/1');assert x['state']=='invalid' and x['reason']=='external_finish' and x['hit_count']==1 and not x['jobs'];assert not {'cast','ability','effect'}&set(x);assert len(events(s,'damage.accepted'))==len(events(s,'projectile.invalid'))==len(events(s,'ability.finished'))==1;assert s.ctx.projectiles._inflight_hits=={};assert not [t for t in s.session.scheduler.pending if t['kind'].startswith('domain.projectile.')]
def test_invalid_callback_new_projectile_id_allowed_and_wait_counts_release_once():
 p=fixture();p['entities'][0]['components']['abilities'].append('ability/child');child=deepcopy(p['abilities'][0]);child['id']='ability/child';child['activation']['parameters']={'blocks_attacks':False};child['timeline'][0]['effect']['projectile_definition']='projectile/child';p['abilities'].append(child);q=deepcopy(p['projectiles'][0]);q['id']='projectile/child';q['on_invalid']=[];q['lifetime_seconds']=0;q['lifecycle']['hit_on_reach']=False;p['projectiles'].append(q);p['selectors'].append({'id':'selector/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'source'}],'limit':1});p['projectiles'][0]['on_invalid']=[{'op':'trigger_ability','ability':'ability/child','selector':'selector/source'}];s=make(p);s.advance(3);assert [e['payload']['projectile'] for e in events(s,'projectile.launched')]==['projectile/1','projectile/2'];assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted')]==[(1,40),(1,40)];assert len(events(s,'ability.finished'))==2 and s.ctx.projectiles._inflight_hits=={};check_replay(s)
def test_terminal_target_damage_and_first_quota_preserve_invalid_history():
 p=fixture();p['entities'][1]['components']['resources']['hp']['initial']=20;p['entities'][1]['components']['lifecycle']={'policy':'policy/ark_lifecycle'};s=make(p);s.advance(3);assert not s.ctx.alive('a') and s.ctx.resources.current('b','hp')==200;assert len(events(s,'projectile.hit'))==1 and len(events(s,'projectile.invalid'))==1;check_replay(s)

@pytest.mark.parametrize('cap,allowed,expected_count',[(1,False,1),(2,True,2)])
def test_reentrant_finite_reservations_allow_only_remaining_slots(cap,allowed,expected_count):
 p=fixture();p['projectiles'][0].update(max_hits=cap,stop_after_first=False,can_hit_same_target=False);s=make(p);original=s.ctx.effects.execute;seen=[];entered=[False]
 def execute(source,targets,effect,ability=None,cast=None,cause=None):
  if (cast or {}).get('projectile_impact') and effect['op']=='damage' and not entered[0]:
   entered[0]=True;x=s.ctx.projectiles._get('projectile/1');seen.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/probe'],s.session.world.resolve('b')))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=execute;s.advance(3);assert seen==[allowed];assert len(events(s,'damage.accepted'))==expected_count;assert s.ctx.projectiles._get('projectile/1')['hit_count']==expected_count and s.ctx.projectiles._inflight_hits=={};assert s.ctx.resources.current('a','hp')==160 and s.ctx.resources.current('b','hp')==(160 if allowed else 200)
