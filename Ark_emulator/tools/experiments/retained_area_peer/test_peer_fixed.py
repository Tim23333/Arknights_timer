from pathlib import Path
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.experiments.retained_buff_payload_peer.test_peer import fixture as single
INPUTS=[];CAPTURES=[]
def fixture():
 p,_=single();p['entities'][1]['tags']=['peer_target']
 member=deepcopy(p['entities'][1]);member['id']='unit/peer/member';outside=deepcopy(member);outside['id']='unit/peer/outside';p['entities']+=[member,outside]
 p['scenarioDraft']['initialEntities'] += [{'definition':member['id'],'instanceAlias':'member','position':{'row':1,'col':2}},{'definition':outside['id'],'instanceAlias':'outside','position':{'row':1,'col':3}}]
 app={'op':'buff_application','application_rule':'rule/peer/cold','allowed':['buff/peer/launched']}
 area={'op':'area','target':3,'radius':1.1,'filters':[{'tag':'peer_target'}],'effects':[{'op':'damage','damage_type':'physical','scale':1},app],'projectile_definition':'projectile/peer/retained'}
 p['abilities'][0]['activation']['on_start']=[area]
 return p,area,app
def make(p,providers=None):INPUTS.append(deepcopy(p));return Engine.create(Compiler(providers=providers).compile(p),seed=62161,providers=providers)
def fire(s):s.submit({'action':'skill','source':'source','ability':'ability/peer/shot'},at=0);s.submit({'action':'skill','source':'controller','ability':'ability/peer/retire_source'},at=2)
def instances(s,who):return thaw(s.ctx.get(who,('buffs','instances'),[]))
def capture(s,name):CAPTURES.append({'case':name,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint(),'area_scopes':deepcopy(s.ctx.projectiles._area_payload_scopes),'impact_scopes':deepcopy(s.ctx.projectiles._impact_payload_scopes),'inflight':deepcopy(s.ctx.projectiles._inflight_hits)})
def exact(s,tmp,n):
 path=tmp/'area_prehit.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,h));s.advance(n);r.advance(n);head=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
def test_true_retained_area_two_actual_members_damage_and_cold_disk_head(tmp_path):
 p,_,_=fixture();s=make(p);fire(s);s.advance(4);exact(s,tmp_path,6);capture(s,'true_two_members')
 assert [(e['payload']['target'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(3,60),(5,60)]
 assert len(instances(s,'target'))==len(instances(s,'member'))==1 and not instances(s,'outside')
 assert not s.ctx.projectiles._area_payload_scopes and not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
def test_literal_outer_unselected_target_cannot_borrow_actual_area_membership():
 p,area,app=fixture();area['effects'].append({**app,'target':6});s=make(p);fire(s);s.advance(10);capture(s,'outer_unselected_literal')
 assert not instances(s,'outside') and len(instances(s,'target'))==len(instances(s,'member'))==1
def test_new_callback_area_has_no_original_packet_cast_authority():
 p,_,app=fixture();p['buffs'][0]['effects']=[{'op':'area','target':3,'center_position':{'row':1,'col':3},'radius':0.1,'filters':[{'tag':'peer_target'}],'effects':[{'op':'buff_application','application_rule':'rule/peer/unlaunched','allowed':['buff/peer/unlaunched']}]}]
 s=make(p);fire(s);s.advance(10);capture(s,'callback_new_area');assert not instances(s,'outside')
def test_callback_activates_in_range_new_target_but_old_membership_does_not_expand():
 p,area,app=fixture();replacement=deepcopy(p['entities'][1]);replacement['id']='unit/peer/replacement';p['entities'].append(replacement);p['scenarioDraft']['initialEntities'].append({'definition':replacement['id'],'instanceAlias':'replacement','active':False,'registration_key':'replacement','position':{'row':0,'col':2}})
 p['buffs'][0]['effects']=[{'op':'activate_predefined','target':'battle','condition':'inputs.targets[0].id == 3','parameters':{'key':'replacement'}}];area['effects'].append({**app,'target':7})
 s=make(p);fire(s);s.advance(10);capture(s,'new_slot_target');assert s.ctx.active('replacement') and not instances(s,'replacement')
def revive(inputs,params,context):return {'action':'revive','resource':'hp','value':1000,'state':'alive'} if inputs['resources']['hp']['current']<=0 else {'action':'none'}
revive.version='peer-area-inline-revive/v1'
def test_nested_overlapping_new_incarnation_cannot_override_outer_original_member_identity():
 p,area,app=fixture();p['rules'].append({'id':'rule/peer/area_revive','kind':'rule','contract':'lifecycle.death','implementation':{'type':'provider','provider':'peer.area_revive'}});p['entities'][3]['components']['lifecycle']['rules']={'lifecycle.death':'rule/peer/area_revive'}
 area['effects']=[{'op':'modify_resource','target':5,'resource':'hp','value':0},{'op':'area','target':3,'radius':1.1,'filters':[{'tag':'peer_target'}],'effects':[app]}]
 s=make(p,{**BUILTIN_PROVIDERS,'peer.area_revive':revive});fire(s);s.advance(10);capture(s,'nested_overlap_incarnation');assert len(instances(s,'target'))==1 and not instances(s,'member') and s.ctx.get('member',('runtime','lifecycle_generation'))==1
def test_true_nested_nonoverlapping_packet_area_selects_its_own_actual_member():
 p,area,app=fixture();area['effects'].append({'op':'area','target':3,'center_position':{'row':1,'col':3},'radius':0.1,'filters':[{'tag':'peer_target'}],'effects':[app]});s=make(p);fire(s);s.advance(10);capture(s,'true_nested_nonoverlap');assert len(instances(s,'outside'))==1
def test_area_fault_rolls_back_all_prior_member_damage_and_clears_every_scope():
 p,_,_=fixture();p['rules'][0]['implementation']['expression']="{'accepted':True,'operations':[{'kind':'apply','buff':'buff/peer/launched','duration_seconds':True}]}";s=make(p);fire(s)
 with pytest.raises(ValueError):s.advance(10)
 capture(s,'area_fault');assert s.ctx.resources.current('target','hp')==s.ctx.resources.current('member','hp')==1000
 assert not s.ctx.projectiles._area_payload_scopes and not s.ctx.projectiles._impact_payload_scopes and not s.ctx.projectiles._inflight_hits
