from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.selection import DEFAULT_STATE
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def box(inputs,params,context):
 states=context['area_selection_states'];source=states['source'];c=inputs['center_position'];out=[]
 for e in inputs['candidates']:
  t=states['candidates'][str(e['id'])];p=e['components']['spatial']['position']
  if max(abs(p['row']-c['row']),abs(p['col']-c['col']))<=1.5 and t['side']!=source['side'] and t['category']&1 and t['motion']&1 and not t['target_free'] and (not t['camouflage'] or source['can_select_camouflage']):out.append(e['id'])
 return out
def oldshape(inputs,params,context):
 assert 'area_selection_states' not in context
 return [e['id'] for e in inputs['candidates']]
def registry():return {**BUILTIN_PROVIDERS,'peer.box':{'callable':box,'version':'1'},'peer.oldshape':{'callable':oldshape,'version':'1'}}
def package():
 area={'op':'area','target':'source','center':'source','membership_rule':'rule/peer/box','selection_projection':{'defaults':deepcopy(DEFAULT_STATE)},'filters':[{'tag':'target'}],'effects':[{'op':'modify_resource','resource':'hp','delta':-11}]}
 p={'schemaVersion':2,'manifest':{'id':'package/peer/projectedbox','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/box','kind':'rule','contract':'area.members','implementation':{'type':'provider','provider':'peer.box'}}],'buffs':[{'id':'buff/peer/camo','kind':'buff','duration_seconds':2/30,'selection_flags':{'abnormal_flags':[17]}},{'id':'buff/peer/free','kind':'buff','selection_flags':{'target_free':True}},{'id':'buff/peer/see','kind':'buff','selection_flags':{'can_select_camouflage':True}}],'abilities':[{'id':'ability/peer/area','kind':'ability','activation':{'mode':'manual'},'timeline':[{'at':3,'effect':area}]},{'id':'ability/peer/camo','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':3,'buff':'buff/peer/camo'}]},'timeline':[]},{'id':'ability/peer/fly','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'set_motion_mode','target':3,'value':1}]},'timeline':[]}],'entities':[{'id':'unit/peer/source','kind':'entity','components':{'selection_state':{'side':1,'motion':1,'category':1},'spatial':{},'abilities':['ability/peer/area','ability/peer/camo','ability/peer/fly']}}],'scenarioDraft':{'id':'scene/peer/projection','ruleset':'ruleset/ark_standard','map':{'rows':7,'cols':7},'objectives':{},'initialEntities':[{'definition':'unit/peer/source','instanceAlias':'source','position':{'row':3,'col':3}}]}}
 for name,pos,state in [('corner',(4.5,4.5),{}),('outside',(4.50001,4.5),{}),('air',(3,3.5),{'motion':2}),('free',(3,3.5),{'target_free':True}),('friend',(3,3.5),{'side':1})]:
  p['entities'].append({'id':'unit/peer/'+name,'kind':'entity','tags':['target'],'components':{'selection_state':{'side':0,'motion':1,'category':1,**state},'attributes':{'base':{'max_hp':101}},'resources':{'hp':{'initial':101,'capacity':101,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'spatial':{}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/'+name,'instanceAlias':name,'position':{'row':pos[0],'col':pos[1]}})
 p['entities'].append({'id':'unit/peer/director','kind':'entity','components':{'abilities':['ability/peer/camo','ability/peer/fly'],'spatial':{}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':0}})
 return p
def make(p=None):p=p or package();INPUTS.append(deepcopy(p));r=registry();return Engine.create(Compiler(providers=r).compile(p),seed=7881,providers=r)
def cmd(s,a,t):s.submit({'action':'skill','source':('source' if a=='area' else 'director'),'ability':'ability/peer/'+a},at=t)
def ev(s,t):return [e for e in s.session.events if e['type']==t]
def capture(s,k):CAPTURES.append({'case':k,'events':thaw(tuple(s.session.events)),'checkpoint':s.checkpoint(),'commands':s.export_replay()})
def test_true_continuous_box_corner_not_circle_and_typed_ground_free_side():
 s=make();cmd(s,'area',0);s.advance(4);capture(s,'box_corner');assert [s.ctx.resources.current(x,'hp') for x in ['corner','outside','air','free','friend']]==[90,101,101,101,101]
def test_live_camo_buff_expiry_at_impact_public_cp_and_head(tmp_path):
 s=make();cmd(s,'area',0);cmd(s,'camo',1);s.advance(2);pin=write_ordered(tmp_path/'projection2.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'projection2.json',pin),providers=registry());s.advance(3);r.advance(3);h=replay(s.program,s.export_replay(),providers=registry());capture(s,'camo_exact_expiry');assert s.checkpoint()==r.checkpoint()==h.checkpoint() and s.ctx.resources.current('corner','hp')==90
def test_live_camo_not_expired_excluded_without_source_see():
 s=make();cmd(s,'area',0);cmd(s,'camo',2);s.advance(4);capture(s,'camo_live');assert s.ctx.resources.current('corner','hp')==101
def test_motion_changed_publicly_before_impact_is_projected_as_flying():
 s=make();cmd(s,'area',0);cmd(s,'fly',1);s.advance(4);capture(s,'fly_at_impact');assert s.ctx.get('corner',('spatial','motion_mode'))==1 and s.ctx.resources.current('corner','hp')==101
@pytest.mark.parametrize('key,value',[('side',True),('motion',1.0),('category',True),('target_free',1),('camouflage','false'),('abnormal_flags',[True])])
def test_projection_defaults_strict_typed_compile(key,value):
 p=package();p['abilities'][0]['timeline'][0]['effect']['selection_projection']['defaults'][key]=value;INPUTS.append(p)
 with pytest.raises(ValueError):Compiler(providers=registry()).compile(p)
def test_no_optin_custom_rule_keeps_old_context_shape():
 p=package();p['abilities'][0]['timeline'][0]['effect'].pop('selection_projection');p['rules'][0]['implementation']['provider']='peer.oldshape';s=make(p);cmd(s,'area',0);s.advance(4);capture(s,'noopt_oldshape');assert len(ev(s,'area.resolved'))==1 and all(s.ctx.resources.current(x,'hp')==90 for x in ['corner','outside','air','free','friend'])
def test_invalid_current_runtime_state_rolls_back_whole_area_before_first_hp_change():
 s=make();cmd(s,'area',0);s.advance(3);s.ctx.set('outside',('selection_state','side'),True)
 with pytest.raises(Exception):s.advance(1)
 capture(s,'bad_live_state');assert not ev(s,'area.resolved') and all(s.ctx.resources.current(x,'hp')==101 for x in ['corner','outside','air','free','friend'])
