import json,hashlib
from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];SOURCE=ROOT/'packages/campaign/chapter04_sources/native.reference.json';raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()=='3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603';SRC=json.loads(raw);INPUTS=[];CAPTURES=[]
PINS={'table':'ff71a061f619069c7063bd1c7e13dfdf4d463b2bfbd5bd96767962c76510e0c2','source_circle':'d2a20696aed4a3c5d693500d4bd2e4c7311181b54f2912adb7bca17755f98bfd'}
def fixture(key,policy='table',route=False,hold=False,high=False):
 path=ROOT/('packages/campaign/chapter04_units/ranged/combat_guard.'+policy+'.reference_model.json');raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==PINS[policy];p=json.loads(raw);uid=next(e['id'] for e in p['entities'] if key in e['id'])
 hero={'id':'unit/probe_guard','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'attributes':{'base':{'max_hp':5000,'def':37,'mres':40,'block_count':1,'taunt_level':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground','parameters':{'max_instances':2}},'abilities':['ability/dash','ability/end_enemy'],'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(hero)
 p['selectors'].append({'id':'selector/probe_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1});p['abilities'].extend([{'id':'ability/dash','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':1,'col':3}}]},'timeline':[]},{'id':'ability/end_enemy','kind':'ability','selector':'selector/probe_enemy','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]}])
 enemy={'definition':uid,'instanceAlias':'enemy','position':{'row':1,'col':1}}
 if route:enemy['route']={'motionMode':0,'startPosition':{'row':1,'col':1},'endPosition':{'row':1,'col':6},'checkpoints':[]}
 if hold:
  p['buffs']=[{'id':'buff/first_tick_hold','kind':'buff','duration_seconds':1/30,'control':{'attack':False}}];enemy['components']={'buffs':{'initial':['buff/first_tick_hold']}}
 p['scenarioDraft']={'id':'scene/c4_ranged_peer','ruleset':'ruleset/ark_standard','roster':['unit/probe_guard'],'map':{'rows':4,'cols':8},'resources':{'dp':{'initial':30,'capacity':30},'life':{'initial':99999,'capacity':99999}},'objectives':{'life_resource':'life'},'initialEntities':[enemy]}
 if high:p['scenarioDraft']['initialEntities'].append({'definition':'unit/probe_guard','instanceAlias':'other','position':{'row':2,'col':1},'components':{'attributes':{'base':{'taunt_level':20}}}})
 return p,uid,hashlib.sha256(raw).hexdigest()
def create(p,h):
 raw=(json.dumps(p,indent=2)+'\n').encode();data={'fixture_sha256':hashlib.sha256(raw).hexdigest(),'fixture':json.loads(raw),'package_sha256':h,'seed':410120};INPUTS.append(data);return Engine.create(Compiler().compile(json.loads(raw)),seed=410120),data

def deploy(s,col=2):s.submit({'action':'deploy','entity':'unit/probe_guard','alias':'guard','position':{'row':1,'col':col}},at=0)
def ev(s,kind):return [e for e in s.session.events if e['type']==kind]
def exact(s,data,tmp,expected):
 s.advance(35);sha=write_ordered(tmp/'cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp/'cp.json',sha));s.advance(15);r.advance(15);assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot();CAPTURES.append({'input':data,'expected':expected,'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay(),'checkpoint_sha256':sha,'checkpoint_equal':True,'replay_equal':True})
@pytest.mark.parametrize('key,frame,amount,lifetime',[('enemy_1012_dcross',20,413,5),('enemy_1011_wizard_2',19,180,10)])
def test_native_stats_clock_projectile_packet_independent_def_res(key,frame,amount,lifetime,tmp_path):
 p,uid,h=fixture(key);s,data=create(p,h);deploy(s);v=next(v for v in SRC['variants'].values() if v['native_reference']['id']==key);base=next(e['components']['attributes']['base'] for e in p['entities'] if e['id']==uid);a=v['native_enemy']['resolved']['attributes'];assert base['max_hp']==a['maxHp'] and base['atk']==a['atk'] and base['def']==a['def'] and base['mres']==a['magicResistance'];assert next(q for q in p['projectiles'] if key in q['id'])['lifetime_seconds']==lifetime
 exact(s,data,tmp_path,{'windup_frame':frame,'speed':10,'range_distance':1,'travel_frames':3,'damage':amount,'DEF':37,'RES':40});ref=s.session.world.resolve('enemy');cast=next(e for e in ev(s,'ability.started') if e['payload']['source']==ref);hit=next(e for e in ev(s,'damage.accepted') if e['payload']['source']==ref);assert hit['time']-cast['time']==frame+3 and hit['payload']['amount']==pytest.approx(amount)

@pytest.mark.parametrize('policy,accepted',[('table',True),('source_circle',False)])
def test_declared_dcross_radius_difference_at_distance2_1(policy,accepted,tmp_path):
 p,uid,h=fixture('enemy_1012_dcross',policy);p['scenarioDraft']['initialEntities'].append({'definition':'unit/probe_guard','instanceAlias':'guard','position':{'row':1,'col':3.1}});s,data=create(p,h);exact(s,data,tmp_path,{'point_distance':2.1,'policy':policy,'has_target':accepted});assert bool(ev(s,'damage.accepted')) is accepted

@pytest.mark.parametrize('key,frame,amount',[('enemy_1012_dcross',20,413),('enemy_1011_wizard_2',19,180)])
def test_launched_packet_retains_retired_source(key,frame,amount,tmp_path):
 p,uid,h=fixture(key);s,data=create(p,h);deploy(s);s.submit({'action':'skill','source':'guard','ability':'ability/end_enemy'},at=frame+1);exact(s,data,tmp_path,{'source_retired_after_launch':frame+1,'expected_impact':frame+3,'amount':amount});assert not s.ctx.alive('enemy') and len(ev(s,'damage.accepted'))==1 and ev(s,'damage.accepted')[0]['payload']['amount']==pytest.approx(amount)


def test_homing_packet_tracks_public_target_motion(tmp_path):
 p,uid,h=fixture('enemy_1012_dcross');s,data=create(p,h);deploy(s);s.submit({'action':'skill','source':'guard','ability':'ability/dash'},at=22);exact(s,data,tmp_path,{'original_target1_2':'moves1_3 at22','windup':20,'actual_impact':26,'damage':413});hit=ev(s,'damage.accepted')[0];assert hit['time']==26 and hit['payload']['amount']==413


def test_dcross_blocked_melee_and_ranged_share_one90tick_clock(tmp_path):
 p,uid,h=fixture('enemy_1012_dcross',route=True,hold=True);s,data=create(p,h);deploy(s,1);s.advance(2);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard')
 # Hold exactly one source tick, solely to establish real blocking before first cast.
 s.advance(92);ref=s.session.world.resolve('enemy');starts=[e for e in ev(s,'ability.started') if e['payload']['source']==ref];assert starts[0]['payload']['ability'].endswith('/combat') and starts[0]['time']==1 and starts[1]['time']==91
 exact(s,data,tmp_path,{'held_first_tick':True,'first_melee_cast':1,'next_melee_cast':91,'each_damage':413});assert all(e['payload']['amount']==413 for e in ev(s,'damage.accepted'))


def test_wizard_source_input_target_cannot_be_overridden_by_unrelated_high_taunt(tmp_path):
 p,uid,h=fixture('enemy_1011_wizard_2',route=True,hold=True,high=True);s,data=create(p,h);deploy(s,1);s.advance(2);blocker=s.session.world.resolve('guard');assert s.ctx.spatial.blocked_by('enemy')==blocker
 exact(s,data,tmp_path,{'source_combat_selectTargetSource':2,'actual_blocker':blocker,'unrelated_taunt':20,'must_target_blocker':True});assert ev(s,'damage.accepted')[0]['payload']['target']==blocker


@pytest.mark.parametrize('taunt',[-1000000,1000000])
def test_wizard_extreme_unrelated_taunt_does_not_override_actual_input_target(taunt,tmp_path):
 p,uid,h=fixture('enemy_1011_wizard_2',route=True,hold=True,high=True);p['scenarioDraft']['initialEntities'][-1]['components']['attributes']['base']['taunt_level']=taunt;s,data=create(p,h);deploy(s,1);s.advance(2);blocker=s.session.world.resolve('guard');assert s.ctx.spatial.blocked_by('enemy')==blocker
 exact(s,data,tmp_path,{'actual_blocker':blocker,'unrelated_taunt':taunt,'must_target_blocker':True});assert ev(s,'damage.accepted')[0]['payload']['target']==blocker


def test_wizard_unselectable_blocker_cannot_fallback_to_other_legal_target(tmp_path):
 p,uid,h=fixture('enemy_1011_wizard_2',route=True,hold=True,high=True);p['scenarioDraft']['initialEntities'].append({'definition':'unit/probe_guard','instanceAlias':'guard','position':{'row':1,'col':1},'components':{'selection_state':{'target_free':True}}});s,data=create(p,h);s.advance(2);assert s.ctx.spatial.blocked_by('enemy')==s.session.world.resolve('guard')
 exact(s,data,tmp_path,{'actual_blocker_unselectable':True,'other_target_is_legal':True,'no_fallback':True});assert not ev(s,'damage.accepted') and not [e for e in ev(s,'ability.started') if e['payload']['source']==s.session.world.resolve('enemy')]
