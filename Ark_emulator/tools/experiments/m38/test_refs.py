"""New source-independent quota fixtures, no author test imports."""
import sys,json,hashlib
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
INPUTS=[]
def motion(inputs,params,context):return {'position':thaw(inputs['positions'][0]['last_target']),'motion_state':{},'reached':params.get('reached',True)}
motion.version='m30-peer-motion-v1'
def collision(inputs,params,context):
 ids=[e['id'] for e in inputs['entities'] if 'extra' in e['tags']]
 return {'hits':ids if context['time']>=params.get('from_tick',2) else [],'stop':False,'terrain_hit':False}
collision.version='m30-peer-collision-v1'
PROVIDERS={**BUILTIN_PROVIDERS,'peer.motion':motion,'peer.collision':collision}
def fixture(cap=None,first=True,same=False):
 def actor(uid,tags):return {'id':uid,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':500,'atk':37,'def':0,'mres':0}},'resources':{'hp':{'initial':500,'capacity':500,'role':'health'}},'spatial':{}}}
 source=actor('unit/source',['enemy']);source['components']['abilities']=['ability/fire']
 return {'manifest':{'requires':['preset/ark_standard']},'entities':[source,actor('unit/a',['player','trace']),actor('unit/b',['player','extra'])],
 'selectors':[{'id':'selector/a','kind':'selector','region':{'type':'all'},'filters':[{'tag':'trace'}],'limit':1}],
 'rules':[{'id':'rule/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'peer.motion'}},{'id':'rule/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'peer.collision'}}],
 'projectiles':[{'id':'projectile/peer','kind':'projectile','motion':{'rule':'rule/motion'},'collision':{'rule':'rule/collision','allow_other_targets':True},'lifetime_seconds':.2,'max_hits':cap,'can_hit_same_target':same,'stop_after_max':True,'stop_after_first':first,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':False,'hit_on_reach':True,'force_reach_on_expire':False,'hit_on_expire':True},'on_invalid':[]}],
 'abilities':[{'id':'ability/fire','kind':'ability','selector':'selector/a','activation':{'mode':'manual','parameters':{'counts_as_attack':True}},'parameters':{'wait_for_projectiles':True},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true','projectile_definition':'projectile/peer'}}]}],
 'scenarioDraft':{'id':'scene/quota_peer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':3},'initialEntities':[{'definition':'unit/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/a','instanceAlias':'a','position':{'row':0,'col':1}},{'definition':'unit/b','instanceAlias':'b','position':{'row':0,'col':2}}]}}
def make(p):
 raw=json.dumps(p,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':3001,'document':json.loads(raw)});s=Engine.create(Compiler(providers=PROVIDERS).compile(json.loads(raw)),seed=3001,providers=PROVIDERS);s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=0);return s
def exact(s):
 r=Engine.restore(s.program,s.checkpoint(),providers=PROVIDERS);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=PROVIDERS).snapshot()
@pytest.mark.parametrize('cap',[None,2])
def test_reach_first_packet_releases_cast_before_later_collision_and_expiry(cap):
 s=make(fixture(cap));s.advance(7)
 assert [(e['time'],e['payload']['target'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(1,s.session.world.resolve('a'),37)]
 assert [e['time'] for e in s.session.events if e['type']=='ability.finished']==[1]
 assert not s.ctx.projectiles._inflight_hits;exact(s)
def test_expiry_zero_and_repeated_paths_obey_total_and_target_caps():
 p=fixture();p['projectiles'][0]['lifetime_seconds']=0;s=make(p);s.advance(1)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(0,37)]
 assert [e['payload']['reason'] for e in s.session.events if e['type']=='projectile.invalid']==['expired'];exact(s)
 p=fixture(None,False,False);s=make(p);s.advance(7)
 assert [(e['time'],e['payload']['target']) for e in s.session.events if e['type']=='damage.accepted']==[(1,s.session.world.resolve('a')),(2,s.session.world.resolve('b'))];exact(s)
def test_nested_numeric_same_target_reservation_blocks_duplicate():
 s=make(fixture(None,False,False));s.advance(1);original=s.ctx.effects.execute;observed=[]
 def nested(source,targets,effect,ability=None,cast=None,cause=None):
  if not observed and (cast or {}).get('projectile_impact'):
   observed.append('entered');x=s.ctx.projectiles._get('projectile/1');observed.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],s.session.world.resolve('a')))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=nested;s.advance(1);assert observed==['entered',False] and s.ctx.resources.current('a','hp')==463
 assert not s.ctx.projectiles._inflight_hits # API instrumentation only, not command replay claim
def test_nested_alias_same_target_is_also_same_actor_reservation():
 s=make(fixture(None,False,False));s.advance(1);original=s.ctx.effects.execute;observed=[]
 def nested(source,targets,effect,ability=None,cast=None,cause=None):
  if not observed and (cast or {}).get('projectile_impact'):
   observed.append('entered');x=s.ctx.projectiles._get('projectile/1');observed.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],'a'))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=nested;s.advance(1);assert observed==['entered',False] and s.ctx.resources.current('a','hp')==463

@pytest.mark.parametrize('outer_alias',[False,True])
def test_api_both_alias_numeric_orders_share_same_target_reservation(outer_alias):
 s=make(fixture(None,False,False));s.advance(1);original=s.ctx.effects.execute;seen=[];target=s.session.world.resolve('a')
 def nested(source,targets,effect,ability=None,cast=None,cause=None):
  if not seen and (cast or {}).get('projectile_impact'):
   seen.append('entered');x=s.ctx.projectiles._get('projectile/1');seen.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],target if outer_alias else 'a'))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=nested;x=s.ctx.projectiles._get('projectile/1')
 with s.session.atomic():assert s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],'a' if outer_alias else target)
 assert seen==['entered',False] and s.ctx.resources.current('a','hp')==463
 assert s.ctx.projectiles._get('projectile/1')['hit_targets']==[target] and not s.ctx.projectiles._inflight_hits

@pytest.mark.parametrize('ref',[True,False,0,-1,999999,'unknown_alias',1.5,[],{}])
def test_invalid_reference_is_read_only_before_quota_reservation(ref):
 s=make(fixture(None,False,False));s.advance(1);x=s.ctx.projectiles._get('projectile/1');before=s.checkpoint()
 with pytest.raises((ValueError,KeyError,TypeError)):s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],ref)
 assert s.checkpoint()==before and not s.ctx.projectiles._inflight_hits

def test_same_target_true_allows_two_mixed_ref_hits_with_finite_two_slots():
 s=make(fixture(2,False,True));s.advance(1);original=s.ctx.effects.execute;seen=[]
 def nested(source,targets,effect,ability=None,cast=None,cause=None):
  if not seen and (cast or {}).get('projectile_impact'):
   seen.append('entered');x=s.ctx.projectiles._get('projectile/1');seen.append(s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],'a'))
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=nested;x=s.ctx.projectiles._get('projectile/1')
 with s.session.atomic():assert s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],s.session.world.resolve('a'))
 assert seen==['entered',True] and s.ctx.resources.current('a','hp')==426 and not s.ctx.projectiles._inflight_hits
 assert s.ctx.projectiles._get('projectile/1')['hit_count']==2

def test_failed_nested_mixed_ref_effect_rolls_back_and_frees_reservations():
 s=make(fixture(None,False,True));s.advance(1);original=s.ctx.effects.execute;seen=[];before=s.checkpoint()
 def nested(source,targets,effect,ability=None,cast=None,cause=None):
  if not seen and (cast or {}).get('projectile_impact'):
   seen.append('entered');x=s.ctx.projectiles._get('projectile/1');s.ctx.projectiles._hit(x,s.program.definitions['projectile/peer'],'a');s.session.random.sample('imp');raise RuntimeError('injected failure after nested actual hit')
  return original(source,targets,effect,ability,cast,cause)
 s.ctx.effects.execute=nested
 with pytest.raises(RuntimeError,match='injected failure'):
  with s.session.atomic():s.ctx.projectiles._hit(s.ctx.projectiles._get('projectile/1'),s.program.definitions['projectile/peer'],s.session.world.resolve('a'))
 assert s.checkpoint()==before and not s.ctx.projectiles._inflight_hits

def test_invalid_callback_failure_preserves_quota_jobs_and_rng():
 p=fixture();p['rules'].append({'id':'rule/failure','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}})
 p['projectiles'][0]['on_invalid']=[{'op':'random','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','target':'source','resource':'hp','delta':-1}]},{'op':'modify_resource','target':'source','resource':'hp','amount_rule':'rule/failure'}]
 s=make(p);s.advance(1);before=s.checkpoint()
 with pytest.raises(Exception,match='division|zero'):
  with s.session.atomic():s.ctx.projectiles._hit(s.ctx.projectiles._get('projectile/1'),s.program.definitions['projectile/peer'],'a')
 assert s.checkpoint()==before and not s.ctx.projectiles._inflight_hits
