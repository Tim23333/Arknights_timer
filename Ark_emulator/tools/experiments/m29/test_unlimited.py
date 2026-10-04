"""No sentinel: unlimited hit cap still obeys life and per-target policies."""
import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m29_storage_projectile_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
INPUTS=[]
def stationary(inputs,parameters,context):return {'position':thaw(inputs['positions'][0]['position']),'motion_state':{},'reached':False}
stationary.version='m28-peer-stationary-v1'
def two_targets(inputs,parameters,context):return {'hits':[e['id'] for e in inputs['entities'] if 'player' in e['tags']],'stop':False,'terrain_hit':False}
two_targets.version='m28-peer-two-targets-v1'
PROVIDERS={**BUILTIN_PROVIDERS,'peer.stationary':stationary,'peer.two':two_targets}
def fixture(cap=None,same=False):
 def entity(uid,tags,hp=1000):return {'id':uid,'kind':'entity','tags':tags,'components':{'attributes':{'base':{'max_hp':hp,'atk':100,'def':0,'mres':0}},'resources':{'hp':{'initial':hp,'capacity':hp,'role':'health'}},'spatial':{}}}
 source=entity('unit/source',['enemy']);source['components']['abilities']=['ability/fire'];source['components']['resources']['sp']={'initial':0,'capacity':10,'recovery_freeze_abilities':[],'recovery_rule':'rule/event','recovery':{'mode':'event','event':'attack.accepted','owner_role':'source','amount':1}}
 return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'entities':[source,entity('unit/target',['player'])],
 'rules':[{'id':'rule/event','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1'}},{'id':'rule/stationary','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'peer.stationary'}}, {'id':'rule/two','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'peer.two'}}],
 'selectors':[{'id':'selector/trace','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}],'limit':1}],
 'projectiles':[{'id':'projectile/probe','kind':'projectile','motion':{'rule':'rule/stationary'},'collision':{'rule':'rule/two','allow_other_targets':True},'lifetime_seconds':.1,'max_hits':cap,'can_hit_same_target':same,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':False,'hit_on_reach':False,'force_reach_on_expire':False,'hit_on_expire':False},'on_invalid':[]}],
 'abilities':[{'id':'ability/fire','kind':'ability','selector':'selector/trace','parameters':{'wait_for_projectiles':True},'activation':{'mode':'manual','parameters':{'counts_as_attack':True}},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true','projectile_definition':'projectile/probe'}}]}],
 'scenarioDraft':{'id':'scenario/unlimited','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':4},'initialEntities':[{'definition':'unit/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/target','instanceAlias':'a','position':{'row':0,'col':1}},{'definition':'unit/target','instanceAlias':'b','position':{'row':0,'col':2}}]}}
def make(p):
 raw=json.dumps(p,sort_keys=True,separators=(',',':')).encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'seed':2801,'document':json.loads(raw)});return Engine.create(Compiler(providers=PROVIDERS).compile(json.loads(raw)),seed=2801,providers=PROVIDERS)
def fire(s):s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=0)
def exact(s):
 r=Engine.restore(s.program,s.checkpoint(),providers=PROVIDERS);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=PROVIDERS).snapshot()

def test_unlimited_two_distinct_targets_dedup_and_lifetime_waiting_cast():
 s=make(fixture());fire(s);s.advance(2)
 assert s.ctx.resources.current('a','hp')==s.ctx.resources.current('b','hp')==900
 assert len([e for e in s.session.events if e['type']=='attack.accepted'])==1 and s.ctx.resources.current('source','sp')==1
 assert not [e for e in s.session.events if e['type']=='ability.finished'];r=Engine.restore(s.program,s.checkpoint(),providers=PROVIDERS);s.advance(2);r.advance(2)
 assert [(e['time'],e['payload']['reason']) for e in s.session.events if e['type']=='projectile.invalid']==[(3,'expired')]
 assert len([e for e in s.session.events if e['type']=='ability.finished'])==1
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay(),providers=PROVIDERS).snapshot()

def test_same_target_repeat_allowed_until_half_open_expiry_and_single_attack_sp():
 s=make(fixture(same=True));fire(s);s.advance(4)
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(1,100),(1,100),(2,100),(2,100)]
 assert s.ctx.resources.current('a','hp')==s.ctx.resources.current('b','hp')==800
 assert s.ctx.resources.current('source','sp')==1;exact(s)

@pytest.mark.parametrize('cap',[None,2])
def test_stop_after_first_overrides_unlimited_or_multiple_finite_cap(cap):
 p=fixture(cap);p['projectiles'][0]['stop_after_first']=True;s=make(p);fire(s);s.advance(3)
 assert len([e for e in s.session.events if e['type']=='damage.accepted'])==1
 assert s.ctx.resources.current('a','hp')==900 and s.ctx.resources.current('b','hp')==1000;exact(s)

def test_stop_after_first_ignores_invalid_first_target_then_hits_valid():
 p=fixture();p['projectiles'][0]['stop_after_first']=True;p['entities'][1]['components']['abilities']=['ability/retire']
 p['abilities'].append({'id':'ability/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]},'timeline':[]})
 s=make(p);fire(s);s.submit({'action':'skill','source':'a','ability':'ability/retire'},at=1);s.advance(3)
 assert len([e for e in s.session.events if e['type']=='damage.accepted'])==1
 assert s.ctx.resources.current('a','hp')==1000 and s.ctx.resources.current('b','hp')==900;exact(s)

@pytest.mark.parametrize('cap',[0,1,2])
def test_finite_capacity_unchanged(cap):
 s=make(fixture(cap));fire(s);s.advance(4)
 assert len([e for e in s.session.events if e['type']=='damage.accepted'])==cap;exact(s)

@pytest.mark.parametrize('cap',[-1,True,1.5,'unlimited'])
def test_invalid_cap_failfast(cap):
 with pytest.raises(ValueError,match='max_hits'):Compiler(providers=PROVIDERS).compile(fixture(cap))

def test_missing_cap_not_implicit_unlimited():
 p=fixture();p['projectiles'][0].pop('max_hits')
 with pytest.raises(ValueError,match='max_hits'):Compiler(providers=PROVIDERS).compile(p)

def test_invalid_callback_rolls_back_world_jobs_events_random():
 p=fixture();p['rules'].append({'id':'rule/fail','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}})
 p['projectiles'][0]['on_invalid']=[{'op':'random','target':'source','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','target':'source','resource':'hp','delta':-1}]},{'op':'modify_resource','target':'source','resource':'hp','amount_rule':'rule/fail'}]
 s=make(p);fire(s);s.advance(2);key=next(iter(s.ctx.projectiles._state()['instances']));before=s.checkpoint()
 with pytest.raises(Exception,match='division|zero'):s.ctx.projectiles.expire(s.session,{'projectile':key})
 assert s.checkpoint()==before
