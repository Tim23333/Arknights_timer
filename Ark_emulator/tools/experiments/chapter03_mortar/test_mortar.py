import json,sys
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m53_qualified_area_candidate'));sys.path.append(str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def fixture():
 p=json.loads((ROOT/'packages/campaign/chapter03_models/mortar.reference.json').read_bytes())
 target={'id':'unit/target','kind':'entity','tags':['player'],'components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':1},'attributes':{'base':{'max_hp':5000,'atk':0,'def':50,'mres':20,'move_speed':0}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'abilities':['ability/move','ability/withdraw']}}
 director={'id':'unit/director','kind':'entity','components':{'spatial':{},'abilities':['ability/boost','ability/retire_source']}}
 p['entities'] += [target,director];p['buffs']=[{'id':'buff/boost','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':100}]}]
 p['selectors'] += [{'id':'selector/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1}]
 p['abilities'] += [{'id':'ability/move','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'move','target':'source','position':{'row':3,'col':5}}]},'timeline':[]},{'id':'ability/withdraw','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':'source','parameters':{'reason':'withdrawn'}}]},'timeline':[]},{'id':'ability/boost','kind':'ability','selector':'selector/source','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/boost'}]},'timeline':[]},{'id':'ability/retire_source','kind':'ability','selector':'selector/source','activation':{'mode':'manual','on_start':[{'op':'retire','parameters':{'reason':'withdrawn'}}]},'timeline':[]}]
 p['scenarioDraft']={'id':'scene/mortar','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':8,'cols':9},'initialEntities':[{'definition':'unit/ch3/mortar','instanceAlias':'mortar','position':{'row':3,'col':0}},{'definition':'unit/target','instanceAlias':'main','position':{'row':3,'col':4}},{'definition':'unit/target','instanceAlias':'neighbor','position':{'row':4,'col':4},'components':{'selection_state':{'motion':2}}},{'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':0}}]};return p
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=5318)
def hits(s):return [e for e in s.session.events if e['type']=='damage.accepted']
def test_source_f16_speed4_one_blast_with_flight_splash():
 s=make();s.advance(50);assert [e['time'] for e in s.session.events if e['type']=='projectile.launched']==[16]
 assert len(hits(s))==2 and [e['time'] for e in hits(s)]==[46,46] and [e['payload']['amount'] for e in hits(s)]==[350,350]
 assert s.ctx.resources.current('main','hp')==4650 and s.ctx.resources.current('neighbor','hp')==4650
 assert len([e for e in s.session.events if e['type']=='projectile.hit'])==1
@pytest.mark.parametrize('patch',[{'target_free':True},{'category':4},{'side':1}])
def test_live_impact_qualifications_reject_splash_members(patch):
 p=fixture();p['scenarioDraft']['initialEntities'][2]['components']['selection_state'].update(patch);s=make(p);s.advance(50)
 assert s.ctx.resources.current('main','hp')==4650 and s.ctx.resources.current('neighbor','hp')==5000
def test_hit_camouflage_allowed_but_primary_camouflage_not_allowed():
 p=fixture();p['scenarioDraft']['initialEntities'][2]['components']['selection_state'].update(camouflage=True);s=make(p);s.advance(50);assert s.ctx.resources.current('neighbor','hp')==4650
 p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'camouflage':True}};s=make(p);s.advance(50);assert not hits(s)
def test_homing_capture_moves_with_public_command_and_late_attributes_are_live(tmp_path):
 p=fixture();p['scenarioDraft']['initialEntities'][2]['position']={'row':4,'col':5};program=Compiler().compile(p);s=Engine.create(program,seed=5319)
 s.submit({'action':'skill','source':'main','ability':'ability/move'},at=30);s.submit({'action':'skill','source':'director','ability':'ability/boost'},at=30);s.advance(25);path=tmp_path/'cp.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(40);r.advance(40)
 assert [e['time'] for e in hits(s)]==[54,54] and [e['payload']['amount'] for e in hits(s)]==[450,450]
 assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
def test_target_retirement_retains_last_point_and_only_living_neighbor_is_hit():
 s=make();s.submit({'action':'skill','source':'main','ability':'ability/withdraw'},at=30);s.advance(50)
 assert not s.ctx.alive('main') and s.ctx.resources.current('neighbor','hp')==4650 and len(hits(s))==1
def test_source_retirement_retains_launched_packet_and_stops_new_attacks():
 s=make();s.submit({'action':'skill','source':'director','ability':'ability/retire_source'},at=30);s.advance(100)
 assert not s.ctx.alive('mortar') and len(hits(s))==2 and len([e for e in s.session.events if e['type']=='projectile.launched'])==1
def test_expiry_fallback_is_once_and_cannot_repeat_blast():
 p=fixture();p['projectiles'][0]['lifetime_seconds']=.1;s=make(p);s.advance(100)
 # Expiry at19 still at the current projectile point, far from the captured target.
 assert not hits(s) and len([e for e in s.session.events if e['type']=='projectile.hit'])==1
def test_flight_primary_is_not_a_ground_primary_and_no_blocker_weight_is_added():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['components']={'selection_state':{'motion':2}};s=make(p);s.advance(50);assert not hits(s)
 assert p['manifest']['metadata']['raw_source']['attack']['_selectTargetSource']==1 and 'score_rule' not in p['selectors'][0]

def test_route_hidden_target_retains_endpoint_for_other_members_without_hitting_hidden_actor():
 p=fixture();p['scenarioDraft']['initialEntities'][1]['route']={'motionMode':0,'startPosition':{'row':3,'col':4},'endPosition':{'row':3,'col':4},'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':1},{'type':'DISAPPEAR'},{'type':'WAIT_FOR_SECONDS','time':3},{'type':'APPEAR_AT_POS','position':{'row':3,'col':4}},{'type':'WAIT_FOR_SECONDS','time':3}]}
 s=make(p);s.advance(50);assert s.ctx.route_hidden('main') and s.ctx.resources.current('main','hp')==5000 and s.ctx.resources.current('neighbor','hp')==4650 and len(hits(s))==1

def test_expiry_first_hit_does_not_double_dispatch_and_cast_clock_remains_single():
 p=fixture();p['projectiles'][0]['lifetime_seconds']=.1;p['scenarioDraft']['initialEntities'][1]['position']={'row':3,'col':.4};p['scenarioDraft']['initialEntities'][2]['position']={'row':4,'col':0}
 s=make(p);s.advance(100);assert len(hits(s))==2 and [e['payload']['amount'] for e in hits(s)]==[350,350]
 assert len([e for e in s.session.events if e['type']=='projectile.hit'])==1

def test_live_target_free_buff_after_launch_blocks_impact_not_neighbor():
 p=fixture();p['buffs'].append({'id':'buff/free','kind':'buff','selection_flags':{'target_free':True}});p['abilities'].append({'id':'ability/free','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':'source','buff':'buff/free'}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/free')
 s=make(p);s.submit({'action':'skill','source':'main','ability':'ability/free'},at=30);s.advance(50);assert s.ctx.resources.current('main','hp')==5000 and s.ctx.resources.current('neighbor','hp')==4650
