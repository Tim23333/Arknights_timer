import json,hashlib
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3];INPUTS=[]
def fixture(target=True):
 p=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.yokai2_move.reference_module.json').read_bytes());uid='unit/chapter02/enemy_1005_yokai_2';initial=[{'definition':uid,'instanceAlias':'drone','position':{'row':0,'col':0},'route':{'motionMode':1,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':3},'checkpoints':[]}}]
 if target:
  p['definitions'].append({'id':'unit/probe','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':10000,'def':100,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'selection_state':{'side':0,'motion':1,'category':1}}});initial.append({'definition':'unit/probe','instanceAlias':'target','position':{'row':0,'col':1.5}})
 p['rules']=[{'id':'rule/fixture/native_half_speed','kind':'rule','contract':'movement.speed','implementation':{'type':'expression','expression':'inputs.movement_parameters.base_speed * .5'}}]
 p['scenarioDraft']={'id':'scene/yokai2_move','ruleset':'ruleset/ark_standard','rules':{'movement.speed':'rule/fixture/native_half_speed'},'objectives':{'life_resource':'lives'},'resources':{'lives':{'initial':99999,'capacity':99999}},'map':{'rows':2,'cols':4},'initialEntities':initial};return p
def make(p):
 raw=(json.dumps(p,indent=2)+'\n').encode();INPUTS.append({'sha256':hashlib.sha256(raw).hexdigest(),'seed':49209,'fixture':json.loads(raw)});return Engine.create(Compiler().compile(json.loads(raw)),seed=49209)
def test_surviving_target_f8_pause_end_then_resume_until_real_exit(tmp_path):
 s=make(fixture());s.advance(1);first=s.ctx.get('drone',('spatial','position'))['col'];s.advance(8);assert s.ctx.get('drone',('spatial','position'))['col']==first
 assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(8,120)]
 s.advance(1);assert s.ctx.get('drone',('spatial','position'))['col']>first
 s.advance(81);assert [e['time'] for e in s.session.events if e['type']=='ability.started']==[0,90]
 path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.advance(170);r.advance(170)
 assert s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','lives')==99998 and s.ctx.resources.current('target','hp')>0
 assert s.ctx.get('drone',('spatial','position'))['row']==0 and s.ctx.get('drone',('spatial','position'))['col']==3
 assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()
def test_no_target_source_speed_half_multiplier_distance_is_real():
 s=make(fixture(False));s.advance(30)
 # Source speed.9 times standard movement multiplier.5; actual 20/100 steering ramps first update.
 assert s.ctx.get('drone',('spatial','position'))['col']==pytest.approx(.4425,abs=.001)
 assert not any(e['type']=='ability.started' for e in s.session.events)
def test_only_one_declared_stop_flag_changes_no_unit_hp_damage_or_stats():
 old=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json').read_bytes());new=json.loads((ROOT/'packages/campaign/chapter02_units/main_02-09.enemies.yokai2_move.reference_module.json').read_bytes());a={d['id']:d for d in old['definitions']};b={d['id']:d for d in new['definitions']};assert {k for k in a if a[k]!=b[k]}=={'behavior/chapter02/yokai_2'}
