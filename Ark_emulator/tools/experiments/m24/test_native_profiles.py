"""The declared source profiles use the actual enemy definitions/selected packets."""
import sys,json
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools.experiments.m24.test_decisions import RUNTIME,ROOT,Compiler,Engine,cp
from tools.build_enemy_fsm_profiles import build
def fixture(key,position):
 p=build('01-12');p['scenarioDraft']={'id':'scenario/source_profile/'+key,'ruleset':'ruleset/ark_standard','roster':[],
  'map':{'rows':8,'cols':11},'waves':[],'objectives':{},'initialEntities':[{'definition':key,'instanceAlias':'enemy','position':{'row':3,'col':3},
   'route':{'motionMode':0,'startPosition':{'row':3,'col':3},'endPosition':{'row':3,'col':9},'checkpoints':[]}}]}
 p['entities'].append({'id':'unit/target_probe','kind':'entity','tags':['player','ground'],'components':{
  'attributes':{'base':{'max_hp':5000,'atk':0,'def':0,'mres':0,'block_count':1}},'resources':{'hp':{'initial':5000,'capacity':5000}},
  'spatial':{},'deployable':{'base_cost':0,'capacity':1,'cooldown_seconds':0,'terrain':'ground'},'abilities':[]}})
 p['scenarioDraft']['initialEntities'].append({'definition':'unit/target_probe','instanceAlias':'target','position':position})
 return p
def test_actual_W_defined_normal_frames_stop_then_targetless_moves():
 p=fixture('unit/chapter01_w',{'row':3,'col':4});s=Engine.create(Compiler().compile(p),seed=24);s.advance(31)
 assert s.ctx.get('enemy',('spatial','position'))=={'row':3,'col':3}
 assert [e['time'] for e in s.session.events if e['type']=='damage.accepted']==[15,29]
 assert s.ctx.resources.current('target','hp')==4060 # actual470 ATK /zeroDEF, two selected full-packet model
 cp(s)
 p=fixture('unit/chapter01_w',{'row':0,'col':0});s=Engine.create(Compiler().compile(p),seed=24);s.advance(4)
 assert s.ctx.get('enemy',('spatial','position'))['col']>3 and not [e for e in s.session.events if e['type']=='ability.started'];cp(s)
def test_actual_mocock_has_selected_target_then_stops():
 p=fixture('unit/enemy_1028_mocock_2',{'row':3,'col':4});s=Engine.create(Compiler().compile(p),seed=24);s.advance(3)
 assert s.ctx.get('enemy',('spatial','position'))=={'row':3,'col':3}
 assert [e for e in s.session.events if e['type']=='ability.started'];cp(s)
def test_actual_rogue_combat_uses_spatial_blocker():
 p=fixture('unit/enemy_1014_rogue',{'row':3,'col':3});s=Engine.create(Compiler().compile(p),seed=24)
 s.ctx.spatial.blocking();assert s.ctx.spatial.blocked_by('enemy')==3;s.advance(4)
 assert s.ctx.get('enemy',('spatial','position'))=={'row':3,'col':3}
 assert [e for e in s.session.events if e['type']=='ability.started']
 # API setup only; checkpoint remains exact. Actual source mode attack-null/combat pointer is audited separately.
 r=Engine.restore(s.program,s.checkpoint());s.advance(2);r.advance(2);assert s.snapshot()==r.snapshot()
