from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def package(flag=True):
 p={'schemaVersion':2,'manifest':{'id':'package/peer/realtiles','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/tileselect','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'graph','nodes':[{'id':'answer','expression':"{'accepted':inputs.candidate_spatial_tile.tile.buildableType == 2,'reason':'actual_tile_mask'}"}],'output':'nodes.answer'}}],'selectors':[{'id':'selector/peer/tile','kind':'selector','region':{'type':'radius','radius':4},'filters':[{'tag':'player'}],'limit':None,'eligibility':{'rule':'rule/peer/tileselect','parameters':{'source_configuration':{'_targetSide':2,'_targetMotion':1,'_targetCategory':1},'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':deepcopy(DEFAULT_STATE)},'include_candidate_tile':flag}}],'entities':[{'id':'unit/peer/source','kind':'entity','tags':['enemy'],'components':{'selection_state':{'side':1,'motion':1,'category':1},'spatial':{}}},{'id':'unit/peer/highGround','kind':'entity','tags':['player','ground'],'components':{'selection_state':{'side':0,'motion':1,'category':1},'spatial':{}}},{'id':'unit/peer/lowRanged','kind':'entity','tags':['player','ranged'],'components':{'selection_state':{'side':0,'motion':1,'category':1},'spatial':{}}}],'scenarioDraft':{'id':'scene/peer/realtiles','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3,'tiles':[{'tileKey':'tile_floor','buildableType':1,'heightType':0,'passableMask':1},{'tileKey':'tile_floor','buildableType':2,'heightType':1,'passableMask':1},{'tileKey':'tile_floor','buildableType':1,'heightType':0,'passableMask':1}]},'objectives':{},'initialEntities':[{'definition':'unit/peer/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/peer/highGround','instanceAlias':'groundOnHigh','position':{'row':0,'col':1}},{'definition':'unit/peer/lowRanged','instanceAlias':'rangedOnLow','position':{'row':0,'col':2}}],'dependencies':['selector/peer/tile']}}
 return p
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p))
def capture(s,k):CAPTURES.append({'case':k,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot(),'commands':s.export_replay()})
def test_actual_tile_mask_selects_ground_on_highland_not_ranged_label_pure():
 s=make(package());before=s.checkpoint();assert s.ctx.spatial.select('source','selector/peer/tile')==[s.session.world.resolve('groundOnHigh')];assert s.checkpoint()==before;capture(s,'tile_vs_label')
@pytest.mark.parametrize('flag',[0,1,None,'true',[]])
def test_optin_flag_is_strict_boolean(flag):
 with pytest.raises(ValueError):Compiler().compile(package(flag))
def test_optin_false_does_not_invent_tile_fields():
 p=package(False);p['rules'][0]['implementation']['nodes'][0]['expression']="{'accepted':'candidate_spatial_tile' not in inputs,'reason':'no_optin'}";s=make(p);assert len(s.ctx.spatial.select('source','selector/peer/tile'))==2;capture(s,'noopt_shape')
