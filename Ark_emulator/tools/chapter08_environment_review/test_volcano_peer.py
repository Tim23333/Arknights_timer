from pathlib import Path
from copy import deepcopy
import json
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[2];MODULE=ROOT/'packages/campaign/chapter08_consumers/environment/volcano.module.v1.json';INPUTS=[];CAPTURES=[]
def package():
 m=json.loads(MODULE.read_bytes());p={'schemaVersion':2,'manifest':{'id':'package/peer/ch8/volcano','requires':['preset/ark_standard']},'rules':deepcopy(m['rules']),'buffs':[{'id':'buff/peer/half','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/peer/half'}]},{'id':'buff/peer/camo','kind':'buff','selection_flags':{'abnormal_flags':[17]}}],'entities':[],'abilities':[{'id':'ability/peer/pose','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':1000,'effect':{'op':'emit','event':'peer.pose.done'}}]},{'id':'ability/peer/half','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':'buff/peer/half'}]},'timeline':[]},{'id':'ability/peer/camo','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':3,'buff':'buff/peer/camo'}]},'timeline':[]}]}
 p['rules'].append({'id':'rule/peer/half','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'half','expression':"{'accepted':True,'amount':inputs.effect.settlement.amount*.5,'allocations':[],'events':[]}"}],'output':'nodes.half'}})
 places=[('center',0,1,1),('enemy_cast',1,1,2),('ally_cast',0,1,2),('enemy_diagonal',1,2,2),('enemy_idle',1,0,1)]
 initial=[]
 for name,side,row,col in places:
  eid='unit/peer/'+name;p['entities'].append({'id':eid,'kind':'entity','components':{'attributes':{'base':{'max_hp':10000,'atk':31,'def':777,'mres':87}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'selection_state':{'side':side,'motion':1,'category':1,'unit_type':1},'abilities':['ability/peer/pose'],'lifecycle':{'policy':'policy/ark_lifecycle'}}});initial.append({'definition':eid,'instanceAlias':name,'position':{'row':row,'col':col}})
 p['entities'].append({'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'selection_state':{'side':0,'motion':1,'category':4,'unit_type':4},'abilities':['ability/peer/half','ability/peer/camo']}});initial.append({'definition':'unit/peer/director','instanceAlias':'director','position':{'row':2,'col':3}})
 tiles=[{'tileKey':'tile_floor','buildableType':1,'passableMask':1,'heightType':0} for _ in range(12)];tiles[5]={'tileKey':'tile_volcano','buildableType':0,'passableMask':1,'heightType':0,'blackboard':[{'key':key,'value':value,'valueStr':None} for key,value in m['manifest']['metadata']['tile_profiles']['tile_volcano']['expected_blackboard'].items()],'effects':None}
 p['scenarioDraft']={'id':'scene/peer/ch8/volcano','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':4,'tiles':tiles,'tile_mechanics':m['manifest']['metadata']['tile_profiles']},'initialEntities':initial};return p
def proof(tmp_path,camo=False):
 p=package();INPUTS.append(deepcopy(p));program=Compiler().compile(p);s=Engine.create(program,seed=81881)
 for alias in ('enemy_cast','ally_cast','enemy_diagonal'):s.submit({'action':'skill','source':alias,'ability':'ability/peer/pose'},at=0)
 s.submit({'action':'skill','source':'director','ability':'ability/peer/half'},at=200)
 if camo:s.submit({'action':'skill','source':'director','ability':'ability/peer/camo'},at=201)
 s.advance(199);pin=write_ordered(tmp_path/'volcano199.json',s.checkpoint());r=Engine.restore(program,load_bound(tmp_path/'volcano199.json',pin));s.advance(202);r.advance(202);h=replay(program,s.export_replay());assert s.checkpoint()==r.checkpoint()==h.checkpoint();CAPTURES.append({'case':'camo' if camo else 'geometry','checkpoint':s.checkpoint(),'snapshot':s.snapshot(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()});return s
def test_selected_cell_plus_combat_orthogonal_policy_excludes_diagonal_ally_and_idle_and_reads_current_hook(tmp_path):
 s=proof(tmp_path);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==2 and {e['payload']['target'] for e in hits}=={2,3};assert s.ctx.resources.current('center','hp')==9500 and s.ctx.resources.current('enemy_cast','hp')==9000
 assert all(s.ctx.resources.current(name,'hp')==10000 for name in ('ally_cast','enemy_diagonal','enemy_idle')) and all(e['payload']['source'] is None for e in hits)
def test_post_creation_camo_flag_at_trigger_excludes_actual_adjacent_casting_enemy(tmp_path):
 s=proof(tmp_path,True);hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['payload']['target']==2 and hits[0]['payload']['amount']==500 and s.ctx.resources.current('enemy_cast','hp')==10000
