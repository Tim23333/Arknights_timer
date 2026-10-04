import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m28_unlimited_projectile_candidate';sys.path.insert(0,str(RUNTIME))
import ark_sim
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
CORE='cb0e7a97a2621aaf4b14dc942181686906733acbcc61f6a5a23ebae9448e997b'
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
 assert implementation_digest()==CORE and Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim';s=Engine.create(Compiler(providers=PROVIDERS).compile(p or fixture()),seed=2802,providers=PROVIDERS);s.submit({'action':'skill','source':'source','ability':'ability/fire'},at=0);return s
def events(s,name):return [e for e in s.session.events if e['type']==name]
def test_stop_first_reach_hit_must_finish_before_future_collision_or_expiry():
 s=make();s.advance(4);assert [(e['time'],e['payload']['amount']) for e in events(s,'damage.accepted')]==[(1,40)];assert s.ctx.resources.current('a','hp')==160 and s.ctx.resources.current('b','hp')==200;assert [e['time'] for e in events(s,'ability.finished')]==[1]
