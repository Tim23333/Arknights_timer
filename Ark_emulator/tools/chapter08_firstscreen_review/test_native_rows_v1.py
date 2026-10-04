from pathlib import Path
from copy import deepcopy
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.chapter08_bsnake.screen_policy_v1 import providers,screen_ray
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/bsnake/first_screen.native7rows.v3.json';INPUTS=[];CAPTURES=[]
def test_native_map_seven_source_row_origins_and_borders_keep_actor_unmoved_cp_head(tmp_path):
 p=json.loads(MODULE.read_bytes());boss=p['entities'][0]['id'];p['entities'].append({'id':'unit/peer/native_director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/native_kill']}});p['abilities'].append({'id':'ability/peer/native_kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'instant_kill','target':2,'parameters':{'cause':'native_row_peer','skip_rebirth':False}}]},'timeline':[]})
 p['scenarioDraft']={'id':'scene/peer/native7source','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':9,'cols':15},'initialEntities':[{'definition':boss,'instanceAlias':'boss','position':{'row':4,'col':10}},{'definition':'unit/peer/native_director','instanceAlias':'director','position':{'row':0,'col':0}}]};INPUTS.append(deepcopy(p));reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg,seed=88817);s.submit({'action':'skill','source':'director','ability':'ability/peer/native_kill'},at=1);s.advance(200);pin=write_ordered(tmp_path/'rows200.json',s.checkpoint());r=Engine.restore(program,load_bound(tmp_path/'rows200.json',pin),providers=reg);s.advance(50);r.advance(50);h=replay(program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint();CAPTURES.append({'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
 launches=[e for e in s.session.events if e['type']=='projectile.launched'];assert len(launches)==7 and [e['time'] for e in s.session.events if e['type']=='source.bsnake.screen.volley']==[211]
 ids=[e['payload']['definition'] for e in launches];assert {int(x.split('/r')[1].split('/')[0]) for x in ids}==set(range(1,8))
 assert s.ctx.get('boss',('spatial','position'))=={'row':4,'col':10}
def test_selected_native_ray_geometry_border1_x1_to13_each_interior_row_is_pure():
 m=json.loads(MODULE.read_bytes());definitions=[p for p in m['projectiles'] if p['id'].endswith('/d0')];values=[]
 for p in definitions:
  state={};point={'row':4,'col':10};parameters=deepcopy(p['motion']['parameters'])
  for tick in range(1,160):
   result=screen_ray({'positions':[{'motion_state':state}],'trajectory_parameters':{'age_seconds':tick/30,'delta_seconds':1/30}},parameters,{'projectile_map_bounds':{'min_row':-.5,'max_row':8.5,'min_col':-.5,'max_col':14.5}});state=result['motion_state'];point=result['position']
   if result['reached']:break
  assert result['reached'] and point['col']==13 and point['row']==parameters['row'] and state['origin']['col']==1
  values.append({'id':p['id'],'end':point,'state':state})
 CAPTURES.append({'case':'pure_native_geometry','values':values});assert len(values)==7
