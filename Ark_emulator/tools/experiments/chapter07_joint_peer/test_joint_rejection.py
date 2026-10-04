from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from ark_sim.domains.selection import DEFAULT_STATE,SWITCHES
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def package():
 p={'schemaVersion':2,'manifest':{'id':'package/peer/joint7','requires':['preset/ark_standard']},'rules':[{'id':'rule/j/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity*inputs.parameters.ratio'}},{'id':'rule/j/tile','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'graph','nodes':[{'id':'answer','expression':"{'accepted':inputs.candidate_spatial_tile.tile.buildableType == 2,'reason':'high_tile'}"}],'output':'nodes.answer'}}], 'selectors':[{'id':'selector/j/aura','kind':'selector','region':{'type':'radius','radius':3},'filters':[{'tag':'recipient'}],'limit':None,'eligibility':{'rule':'rule/j/tile','include_candidate_tile':True,'parameters':{'source_configuration':{**{k:0 for k in SWITCHES},'_targetSide':7,'_targetMotion':3,'_targetCategory':7},'side_policy':'relative_ally_enemy','neutral_policy':'absolute_mask','defaults':deepcopy(DEFAULT_STATE)}}}], 'buffs':[{'id':'buff/j/parent','kind':'buff','removal':{'on_source_death':'retain','on_target_death':'retain'},'aura':{'selector':'selector/j/aura','buff':'buff/j/child','lease_policy':{'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject','owner_activity':'active_or_rebirth_waiting'}}},{'id':'buff/j/child','kind':'buff','stacking':{'mode':'refresh','max_stacks':1},'modifiers':[{'attribute':'atk','layer':'flat','value':37}]},{'id':'buff/j/timer','kind':'buff','interval_seconds':29/30,'removal':{'on_source_death':'retain','on_target_death':'retain'},'effects':[{'op':'trigger_ability','target':'source','ability':'ability/j/wait'}]}], 'abilities':[{'id':'ability/j/wait','kind':'ability','duration_seconds':.5,'activation':{'mode':'manual','parameters':{'auto_only':True}},'timeline':[{'at':3,'effect':{'op':'emit','event':'peer.joint.impact'}}]},{'id':'ability/j/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'modify_resource','target':2,'resource':'hp','value':0}]},'timeline':[]},{'id':'ability/j/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdraw'}}]},'timeline':[]}], 'entities':[], 'scenarioDraft':{'id':'scene/joint7','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':4,'tiles':[{'tileKey':'tile_floor','buildableType':m,'heightType':int(m==2),'passableMask':1} for m in [2,2,1,2]]},'initialEntities':[]}}
 for name,col in [('owner',0),('ally',1),('low',2),('dormant',3)]:
  c={'attributes':{'base':{'max_hp':123,'atk':19}},'resources':{'hp':{'initial':123,'capacity':123,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'selection_state':{'side':1,'motion':1,'category':1},'spatial':{}}
  if name=='owner':c.update(buffs={'initial':['buff/j/parent','buff/j/timer']},abilities=['ability/j/wait'],rebirth={'resource':'hp','max_count':1,'delay_seconds':100/30,'restore_ratio':1,'restore_rule':'rule/j/restore','retain_buffs':['buff/j/parent','buff/j/timer'],'waiting_actions':{'abilities':['ability/j/wait'],'buffs':['buff/j/timer']}})
  p['entities'].append({'id':'unit/j/'+name,'kind':'entity','tags':['recipient'],'components':c});row={'definition':'unit/j/'+name,'instanceAlias':name,'position':{'row':0,'col':col}}
  if name=='dormant':row.update(active=False,registration_key='peer-dormant')
  p['scenarioDraft']['initialEntities'].append(row)
 p['entities'].append({'id':'unit/j/controller','kind':'entity','components':{'abilities':['ability/j/kill','ability/j/retire'],'spatial':{}}});p['scenarioDraft']['initialEntities'].append({'definition':'unit/j/controller','instanceAlias':'controller','position':{'row':0,'col':3}})
 return p
def make(p=None):
 p=p or package();INPUTS.append(deepcopy(p));s=Engine.create(Compiler().compile(p),seed=7013);s.submit({'action':'skill','source':'controller','ability':'ability/j/kill'},at=1);return s
def children(s,a):return [b for b in s.ctx.get(a,('buffs','instances'),[]) if b['definition']=='buff/j/child']
def capture(s,k):CAPTURES.append({'case':k,'input_replay':s.export_replay(),'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'snapshot':s.snapshot()})
def test_true_waiting_self_and_ally_high_tile_only_with_disk_head(tmp_path):
 s=make();s.advance(28);assert not s.ctx.active('owner') and s.ctx.alive('owner') and s.ctx.resources.current('owner','hp')==0
 assert len(children(s,'owner'))==len(children(s,'ally'))==1 and not children(s,'low') and not children(s,'dormant')
 assert s.ctx.get('owner',('attributes','modifiers'))[0]['value']==37
 pin=write_ordered(tmp_path/'joint28.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'joint28.json',pin));s.advance(76);r.advance(76);h=replay(s.program,s.export_replay());capture(s,'waiting_joint_disk')
 assert s.checkpoint()==r.checkpoint()==h.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(h.session.events));assert any(e['type']=='peer.joint.impact' and e['time']==32 for e in s.session.events)
def test_foreign_parent_uid_never_grants_inactive_source_selection():
 s=make();s.advance(2);uid=s.ctx.get('owner',('buffs','instances'))[0]['id'];before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.spatial.select('owner','selector/j/aura',aura_parent='foreign-parent')
 from ark_sim.domains.shared_auras import selection_target_allowed
 assert not selection_target_allowed(s.ctx,'ally',s.session.world.resolve('owner'),s.program.definitions['selector/j/aura'],uid)
 capture(s,'foreign_parent');assert s.ctx.resources.current('owner','hp')==0
def test_removing_actual_retained_parent_cleans_self_ally_but_keeps_timer():
 s=make();s.advance(30);parent=next(b for b in s.ctx.get('owner',('buffs','instances')) if b['definition']=='buff/j/parent');s.ctx.buffs.remove('owner',parent['id']);assert not children(s,'owner') and not children(s,'ally');s.advance(4);capture(s,'parent_removed');assert any(e['type']=='peer.joint.impact' for e in s.session.events)
def test_public_retirement_cancels_waiting_and_shared_children():
 s=make();s.submit({'action':'skill','source':'controller','ability':'ability/j/retire'},at=30);s.advance(35);capture(s,'public_retire');assert not children(s,'owner') and not children(s,'ally') and not any(e['type']=='peer.joint.impact' for e in s.session.events)
def test_foreign_cast_task_cannot_borrow_joint_aura_permission():
 s=make();s.advance(30);c=next(iter(s.ctx.get('owner',('runtime','casts')).values()));s.session.schedule('domain.ability.effect',{'source':2,'cast':c['id'],'effect':{'op':'emit','event':'peer.joint.forged'}},31,phase=s.ctx.effect_phase);s.advance(5);capture(s,'foreign_cast');assert not any(e['type']=='peer.joint.forged' for e in s.session.events)
