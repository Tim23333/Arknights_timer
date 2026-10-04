import sys,json,math
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];CANDIDATE=ROOT.parent/'unpack_work/campaign_m17_projectile_candidate';sys.path.insert(0,str(CANDIDATE));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from ark_sim.adapters.api import implementation_digest
from tools.build_chapter01_w_combat import fixture
from tools.experiments.chapter01_projectiles.build_model import build

def events(s,t):return [e for e in s.session.events if e['type']==t]
def base(attachment='fixed',normal=True,targets=((3,4),)):
 p=fixture(build(attachment=attachment),positions=targets)
 if not normal:
  unit=p['entities'][0];unit['components']['abilities']=[a for a in unit['components']['abilities'] if not a.startswith('ability/chapter01_w_normal_')];unit['components']['resources']['c4_clock_0']['initial']=20
 p['abilities'].append({'id':'ability/target_move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':3,'col':7}}]},'parameters':{'blocks_attacks':False},'timeline':[]})
 target=next(e for e in p['entities'] if e['id']=='unit/chapter01_w_target');target['components']['abilities']=['ability/target_move']
 return p

def make(p):
 s=Engine.create(Compiler().compile(p),seed=1701);assert Path(sys.modules['ark_sim'].__file__).resolve().is_relative_to(CANDIDATE.resolve());return s

def cp(s):
 before=implementation_digest();r=Engine.restore(s.program,s.checkpoint(),providers=s.ctx.providers);s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot();assert s.snapshot()==replay(s.program,s.export_replay(),providers=s.ctx.providers).snapshot();assert implementation_digest()==before

@pytest.mark.parametrize('phase',[0,1])
def test_normal_actual_frames_and_single_hit_quota(phase):
 p=base();p['entities'][0]['components']['resources']['mode']['initial']=phase
 if phase:p['entities'][0]['components']['resources']['hp']['initial']=5000
 s=make(p);s.advance(31);assert [e['time'] for e in events(s,'projectile.launched')]==[9,23];assert [e['time'] for e in events(s,'damage.accepted')]==[15,29];assert [e['payload']['amount'] for e in events(s,'damage.accepted')]==[370,370];assert s.ctx.resources.current('target0','hp')==4260
 instances=s.ctx.get('system/battle',('projectiles','instances'));assert all(x['hit_count']==1 and not x['jobs'] and x['state']=='invalid' for x in instances.values());cp(s)

def test_moving_target_homing_is_actual_recorded_command():
 p=base();move=next(a for a in p['abilities'] if a['id']=='ability/target_move');move['activation']['on_start'][0]['position']['col']=5
 s=make(p);s.submit({'action':'skill','source':'target0','ability':'ability/target_move'},at=10);s.advance(36)
 assert [e['time'] for e in events(s,'damage.accepted')]==[21,35];assert all(e['payload']['target']==s.session.world.resolve('target0') for e in events(s,'damage.accepted'));assert len(events(s,'command.accepted'))==1;cp(s)

@pytest.mark.parametrize('attachment',['fixed','follow'])
def test_C4_attachment_position_area_and_pending_cast(attachment):
 s=make(base(attachment,False,((3,4),(3,5))));s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);s.submit({'action':'skill','source':'target0','ability':'ability/target_move'},at=50);s.advance(113)
 assert not events(s,'damage.accepted');casts=s.ctx.get('w',('runtime','casts'));assert len(casts)==1 and next(iter(casts.values()))['pending_projectiles']==1
 restored=Engine.restore(s.program,s.checkpoint(),providers=s.ctx.providers);s.advance(2);restored.advance(2);assert s.snapshot()==restored.snapshot()
 assert all(e['time']==114 for e in events(s,'damage.accepted'));assert not s.ctx.get('w',('runtime','casts'))
 center=events(s,'area.resolved')[0]['payload']['center'];assert center=={'row':3,'col':4 if attachment=='fixed' else 7}
 assert s.ctx.resources.current('target0','hp')==(5000 if attachment=='fixed' else 4254);assert s.ctx.resources.current('target1','hp')==4254
 assert [e['type'] for e in s.session.events if e['time']==114 and e['type'] in ('projectile.reached','projectile.hit','projectile.invalid','ability.finished')]==['projectile.reached','projectile.hit','projectile.invalid','ability.finished'];cp(s)

@pytest.mark.parametrize('who',['w','target0'])
def test_normal_source_or_target_withdraw_policies(who):
 s=make(base());s.submit({'action':'withdraw','source':who},at=10);s.advance(31)
 assert len(events(s,'command.accepted'))==1
 assert len(events(s,'damage.accepted'))==(1 if who=='w' else 0)
 assert s.ctx.resources.current('target0','hp')==(4630 if who=='w' else 5000);cp(s)

def test_C4_target_retirement_retains_point_and_hits_living_neighbor():
 s=make(base(normal=False,targets=((3,4),(3,5))));s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);s.submit({'action':'withdraw','source':'target0'},at=50);s.advance(115)
 assert s.ctx.resources.current('target0','hp')==5000 and s.ctx.resources.current('target1','hp')==4254;assert len(events(s,'damage.accepted'))==1;cp(s)

def test_expiry_forced_end_hit_no_repeated_collision():
 p=base();d=p['projectiles'][0];d['motion']['parameters']['speed']=0;d['lifetime_seconds']=.2
 s=make(p);s.advance(31);assert [e['time'] for e in events(s,'damage.accepted')]==[15,29];assert len(events(s,'projectile.invalid'))==2;assert all(e['payload']['reason']=='expired' for e in events(s,'projectile.invalid'));cp(s)

@pytest.mark.parametrize('bad',['missing_policy','bad_bool','wrong_rule_contract','wrong_reference_kind','negative_life'])
def test_strict_content_negative(bad):
 p=base()
 if bad=='missing_policy':p['projectiles'][0]['lifecycle'].pop('target_hidden')
 elif bad=='bad_bool':p['projectiles'][0]['stop_after_max']=1
 elif bad=='wrong_rule_contract':p['projectiles'][0]['motion']['rule']='rule/ark_projectile_speed'
 elif bad=='wrong_reference_kind':next(a for a in p['abilities'] if a['id'].startswith('ability/chapter01_w_normal_'))['timeline'][0]['effect']['projectile_definition']='unit/chapter01_w'
 else:p['projectiles'][0]['lifetime_seconds']=-1
 with pytest.raises(ValueError):Compiler().compile(p)


def killer(p,target):
 p['entities'].append({'id':'unit/kill_probe','kind':'entity','tags':['player'],'components':{'attributes':{'base':{'max_hp':100,'atk':100000,'def':0,'mres':0}},'spatial':{},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'abilities':['ability/kill_probe']}})
 p['scenarioDraft']['initialEntities'].append({'definition':'unit/kill_probe','instanceAlias':'probe','position':{'row':0,'col':0}})
 selected=p['entities'][0] if target=='w' else next(e for e in p['entities'] if e['id']=='unit/chapter01_w_target');selected['tags'].append('kill_selected')
 p['selectors'].append({'id':'selector/kill_probe','kind':'selector','region':{'type':'all'},'filters':[{'tag':'kill_selected'},{'state':'alive'}],'limit':1})
 p['abilities'].append({'id':'ability/kill_probe','kind':'ability','selector':'selector/kill_probe','activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'true','scale':1}]},'timeline':[]})

@pytest.mark.parametrize('target',['w','target0'])
def test_actual_damage_death_policy(target):
 p=base();killer(p,target);s=make(p);s.submit({'action':'skill','source':'probe','ability':'ability/kill_probe'},at=10);s.advance(31)
 assert not s.ctx.alive(target) and s.ctx.resources.current(target,'hp')==0 and events(s,'entity.died')
 normal=[e for e in events(s,'damage.accepted') if str(e['payload'].get('ability','')).startswith('ability/chapter01_w_normal_')];assert len(normal)==(1 if target=='w' else 0);cp(s)

def test_hidden_captured_target_cannot_bypass_policy():
 p=base();target=next(e for e in p['entities'] if e['id']=='unit/chapter01_w_target');target['components']['attributes']['base']['move_speed']=3
 p['scenarioDraft']['initialEntities'][1]['route']={'motionMode':'WALK','endPosition':{'row':3,'col':8},'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},'checkpoints':[{'type':'MOVE','position':{'row':3,'col':5.1}},{'type':'DISAPPEAR'},{'type':'WAIT_FOR_SECONDS','time':1},{'type':'APPEAR_AT_POS','position':{'row':3,'col':5.1}}]}
 s=make(p);s.advance(31);assert s.ctx.route_hidden('target0');assert events(s,'projectile.launched') and any(e['payload']['reason']=='target_hidden' for e in events(s,'projectile.invalid'));assert not events(s,'damage.accepted');cp(s)

def test_multiple_C4_objects_wait_exactly_once():
 p=base(normal=False,targets=((3,4),(4,4),(2,4)));u=p['entities'][0];u['components']['resources']['mode']['initial']=1;u['components']['resources']['hp']['initial']=5000;u['components']['resources']['c4_clock_1']['initial']=20
 s=make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_1'},at=0);s.advance(113);assert next(iter(s.ctx.get('w',('runtime','casts')).values()))['pending_projectiles']==3;s.advance(2)
 assert len(events(s,'projectile.launched'))==3 and len(events(s,'projectile.invalid'))==3 and len(events(s,'damage.accepted'))==9
 assert len([e for e in events(s,'ability.finished') if e['payload']['ability']=='ability/chapter01_w_c4_1'])==1
 assert all(s.ctx.resources.current('target'+str(i),'hp')==2762 for i in range(3));cp(s)

def wall_collision(inputs,params,context):
 return {'hits':[],'terrain_hit':inputs['projectile']['position']['col']>=3.1,'stop':inputs['projectile']['position']['col']>=3.1}
wall_collision.version='independent-wall-column-model-1'

def test_replaceable_collision_policy_stops_owned_jobs():
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 providers={**BUILTIN_PROVIDERS,'review.wall':wall_collision};p=base();p['rules'].append({'id':'rule/review/wall','kind':'calculation_rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'review.wall'}});p['projectiles'][0]['collision']['rule']='rule/review/wall'
 s=Engine.create(Compiler(providers=providers).compile(p),seed=1701,providers=providers);s.advance(31);assert not events(s,'damage.accepted');assert len(events(s,'projectile.invalid'))==2 and all(e['payload']['reason']=='terrain_collision' for e in events(s,'projectile.invalid'));cp(s)

def test_expiry_callback_failure_all_domain_state_atomic():
 p=base(normal=False);p['scenarioDraft']['resources']['dp']['initial']=10
 p['rules'].append({'id':'rule/review/fault','kind':'calculation_rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1 / 0'}})
 p['projectiles'][1]['on_invalid']=[{'op':'random','target':'source','stream':'imp','probability':1,'on_success':[{'op':'modify_resource','target':'battle','resource':'dp','delta':2}]},{'op':'modify_resource','target':'battle','resource':'dp','amount_rule':'rule/review/fault'}]
 s=make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);observed={};original=s.session._handlers['domain.projectile.expire']
 def boundary(session,payload):observed['before']=session.snapshot();return original(session,payload)
 s.session._handlers['domain.projectile.expire']=boundary
 with pytest.raises(Exception):s.advance(115)
 after=s.checkpoint();before={'kernel':observed['before']};assert after['kernel']['world']==before['kernel']['world'] and after['kernel']['random']==before['kernel']['random'] and after['kernel']['events']==before['kernel']['events'] and after['kernel']['scheduler']==before['kernel']['scheduler'];assert after['kernel']['failure'] is not None and 'division by zero' in json.dumps(after['kernel']['failure']).lower()
 with pytest.raises(Exception):s.advance(1)


def test_late_old_packet_cannot_recover_SP_after_newer_cast():
 p=base();unit=p['entities'][0];unit['components']['abilities']=['ability/review/fire'];unit['components']['resources']['sp']={'initial':0,'capacity':10}
 slow=deepcopy(p['projectiles'][0]);slow.update(id='projectile/review/slow');slow['motion']['parameters']['mode']='fixed';slow['collision']['parameters']['enabled']=False;p['projectiles'].append(slow)
 p['abilities'].append({'id':'ability/review/fire','kind':'ability','activation':{'mode':'manual','parameters':{'counts_as_attack':True,'sp_resource':'sp','recovery_per_attack':1}},'selector':'selector/chapter01_w_normal_0','timeline':[{'at_seconds':.3,'effect':{'op':'damage','damage_type':'physical','scale':1,'projectile_definition':'projectile/chapter01_w/normal'}},{'at_seconds':23/30,'effect':{'op':'damage','damage_type':'physical','scale':1,'projectile_definition':slow['id']}}]})
 s=make(p);s.submit({'action':'skill','source':'w','ability':'ability/review/fire'},at=0);s.submit({'action':'skill','source':'w','ability':'ability/review/fire'},at=24);s.advance(324)
 assert [e['time'] for e in events(s,'damage.accepted')]==[15,39,323];assert s.ctx.resources.current('w','sp')==2;assert len(events(s,'attack.accepted'))==2;cp(s)


def duplicate_collision(inputs,params,context):
 return {'hits':[inputs['projectile']['trace_target']]*4,'terrain_hit':False,'stop':False}
duplicate_collision.version='independent-four-contact-model-1'

@pytest.mark.parametrize('same',[False,True])
def test_duplicate_collision_respects_identity_and_quota(same):
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 providers={**BUILTIN_PROVIDERS,'review.duplicate':duplicate_collision};p=base();p['rules'].append({'id':'rule/review/duplicates','kind':'calculation_rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'review.duplicate'}});d=p['projectiles'][0];d['collision']['rule']='rule/review/duplicates';d['max_hits']=2;d['can_hit_same_target']=same
 s=Engine.create(Compiler(providers=providers).compile(p),seed=1701,providers=providers);s.advance(31)
 assert len(events(s,'damage.accepted'))==(4 if same else 2);assert all(x['hit_count']==(2 if same else 1) for x in s.ctx.get('system/battle',('projectiles','instances')).values());cp(s)

def test_nested_on_invalid_projectile_counts_then_finishes_once():
 p=base(normal=False);normal=p['projectiles'][0];normal['collision']['parameters']['enabled']=False;normal['motion']['parameters']['speed']=0;normal['lifetime_seconds']=.1
 p['projectiles'][1]['on_invalid']=[{'op':'damage','damage_type':'physical','scale':1,'projectile_definition':normal['id']}]
 s=make(p);s.submit({'action':'skill','source':'w','ability':'ability/chapter01_w_c4_0'},at=0);s.advance(115)
 assert len(events(s,'projectile.launched'))==2 and len(events(s,'projectile.invalid'))==1 and next(iter(s.ctx.get('w',('runtime','casts')).values()))['pending_projectiles']==1
 s.advance(3);assert [e['time'] for e in events(s,'damage.accepted')]==[114,117];assert len(events(s,'ability.finished'))==1 and events(s,'ability.finished')[0]['time']==117;cp(s)

def test_source_cancel_policy_is_explicit_not_default():
 p=base();p['projectiles'][0]['lifecycle']['source_invalid']='cancel';s=make(p);s.submit({'action':'withdraw','source':'w'},at=10);s.advance(31)
 assert not events(s,'damage.accepted');assert events(s,'projectile.invalid')[0]['payload']['reason']=='source_invalid';cp(s)


def other_collision(inputs,params,context):
 return {'hits':['target1'],'terrain_hit':False,'stop':False}
other_collision.version='independent-other-actor-contact-1'

@pytest.mark.parametrize('allow',[False,True])
def test_collision_output_other_actor_requires_explicit_policy(allow):
 from ark_sim.domains.providers import BUILTIN_PROVIDERS
 providers={**BUILTIN_PROVIDERS,'review.other':other_collision};p=base(targets=((3,4),(3,5)));p['rules'].append({'id':'rule/review/other','kind':'calculation_rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'review.other'}});p['projectiles'][0]['collision'].update(rule='rule/review/other',allow_other_targets=allow)
 s=Engine.create(Compiler(providers=providers).compile(p),seed=1701,providers=providers)
 if not allow:
  with pytest.raises(ValueError,match='outside captured'):s.advance(31)
  assert s.ctx.resources.current('target0','hp')==5000 and s.ctx.resources.current('target1','hp')==5000
 else:
  s.advance(31);assert s.ctx.resources.current('target0','hp')==5000 and s.ctx.resources.current('target1','hp')==4260;cp(s)
