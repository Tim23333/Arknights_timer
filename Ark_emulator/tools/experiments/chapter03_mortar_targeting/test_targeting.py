import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m56_chapter03_integrated_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def base():return json.loads((ROOT/'packages/campaign/chapter03_models/mortar.targeting.reference.json').read_bytes())
def enemy_route(start=0,end=3):return {'motionMode':0,'startPosition':{'row':0,'col':start},'endPosition':{'row':0,'col':end},'checkpoints':[]}
def fixture_priority(free=False):
 p=base();observer={'id':'unit/target','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'category':1,'motion':1},'attributes':{'base':{'max_hp':10000,'def':50,'mres':0,'block_count':1,'taunt_level':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'deployable':{'base_cost':0,'terrain':'ground'}}};p['entities'].append(observer)
 p['buffs']=[{'id':'buff/peer/preblock','kind':'buff','duration_seconds':1/30,'control':{'attack':False}}]
 p['scenarioDraft']={'id':'scene/mortar/reference_blocker','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':2,'cols':5},'initialEntities':[{'definition':'unit/ch3/mortar','instanceAlias':'mortar','position':{'row':0,'col':0},'route':enemy_route(),'components':{'buffs':{'initial':['buff/peer/preblock']}}},{'definition':'unit/target','instanceAlias':'blocker','position':{'row':0,'col':0},'components':{'selection_state':{'target_free':free}}},{'definition':'unit/target','instanceAlias':'taunt','position':{'row':0,'col':1},'components':{'attributes':{'base':{'block_count':0,'taunt_level':20}}}}]};return p
def make(p):return Engine.create(Compiler().compile(p),seed=5356)
def test_real_blocker_eligibility_cannot_be_overridden_by_extreme_taunt():
 s=make(fixture_priority());s.advance(25);launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==1 and launches[0]['payload']['target']==s.session.world.resolve('blocker')
 assert s.ctx.spatial.blocked_by('mortar')==s.session.world.resolve('blocker')
def test_free_blocker_has_no_fallback_to_other_taunt_target():
 s=make(fixture_priority(True));s.advance(25);assert not [e for e in s.session.events if e['type']=='projectile.launched']
def test_unblocked_source_category_and_ground_range_still_gate_primary():
 p=fixture_priority();p['entities'][1]['components']['attributes']['base']['block_count']=0;p['scenarioDraft']['initialEntities'][0].pop('route');s=make(p);s.advance(25)
 assert [e['payload']['target'] for e in s.session.events if e['type']=='projectile.launched']==[s.session.world.resolve('taunt')]
 assert p['manifest']['metadata']['raw_source']['attack']['_selectTargetSource']==1 and p['selectors'][0]['eligibility']['parameters']['source_configuration']['_targetCategory']==1
def fixture_obstacle(two=False):
 p=base();crate=json.loads((ROOT/'packages/campaign/chapter03_traps/crate.partial.reference_model.json').read_bytes())['entities'][0];crate['components']['route_obstacle']={'rule':'rule/peer/obstacle','contact_radius':.45,'parameters':{}};p['entities'].append(crate)
 p['rules'].append({'id':'rule/peer/obstacle','kind':'rule','contract':'blocking.obstacle','implementation':{'type':'expression','expression':'inputs.source.components.selection_state.side != inputs.obstacle.components.selection_state.side'}})
 neighbor={'id':'unit/air_neighbor','kind':'entity','tags':['player'],'components':{'spatial':{'motion_mode':1},'selection_state':{'side':0,'category':1,'motion':2},'attributes':{'base':{'max_hp':10000,'atk':0,'def':50,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}}}}
 director={'id':'unit/director','kind':'entity','components':{'spatial':{},'selection_state':{'side':2,'motion':0,'category':0},'abilities':['ability/neighbor']}}
 p['entities'] += [neighbor,director];p['abilities'].append({'id':'ability/neighbor','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'spawn','definition':'unit/air_neighbor','position':{'row':0,'col':2}}]},'timeline':[]})
 p['scenarioDraft']={'id':'scene/mortar/native_crate','ruleset':'ruleset/ark_standard','roster':['unit/ch3/crate'],'resources':{'dp':{'initial':50,'capacity':100},'crate_cards':{'initial':5,'capacity':5},'life':{'initial':99999,'capacity':99999}},'objectives':{'type':'waves','life_resource':'life'},'map':{'rows':1,'cols':4},'initialEntities':[{'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':3}}],
 'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':[{'pre_delay_seconds':.1,'fragments':[{'actions':[{'kind':'spawn','spawn':{'definition':'unit/ch3/mortar','instanceAlias':'mortar','position':{'row':0,'col':0},'route':enemy_route()}}]}]}]}}
 return p
def submit_obstacle(s,two=False):
 s.submit({'action':'deploy','definition':'unit/ch3/crate','alias':'crate','position':{'row':0,'col':1}},at=0)
 if two:s.submit({'action':'deploy','definition':'unit/ch3/crate','alias':'crate2','position':{'row':0,'col':2}},at=0)
 s.submit({'action':'skill','source':'director','ability':'ability/neighbor'},at=30)
def test_native_crate_contact_f16_one_captured_primary_and_air_splash_then_real_leak(tmp_path):
 p=fixture_obstacle();program=Compiler().compile(p);s=Engine.create(program,seed=5357);submit_obstacle(s);s.advance(35);path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(170);r.advance(170)
 launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==1 and launches[0]['payload']['target']==s.session.world.resolve('crate')
 starts=[e for e in s.session.events if e['type']=='ability.started' and e['payload'].get('ability')=='ability/ch3/mortar/obstacle'];assert len(starts)==1 and launches[0]['time']-starts[0]['time']==16
 packets=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(packets)==2 and [e['payload']['amount'] for e in packets]==[100,350]
 assert [e['payload']['value']['amount'] for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='damage.pipeline']==[400,350]
 assert not s.ctx.alive('crate') and s.ctx.resources.current('crate','hp')==0 and s.ctx.resources.current('system/battle','crate_cards')==4
 assert s.ctx.state()['kills']==0 and s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','life')==99998 and not s.ctx.state()['terrain']['layers']
 assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
def test_neighbor_category4_is_not_granted_special_primary_permissions():
 s=make(fixture_obstacle(True));submit_obstacle(s,True);s.advance(65);assert not s.ctx.alive('crate') and s.ctx.alive('crate2') and s.ctx.resources.current('crate2','hp')==100
 assert len([e for e in s.session.events if e['type']=='projectile.launched'])==1
