from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.buff_application import pure_attributes
from ark_sim.domains.rebirth_self_buffs import retained
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
BOOST='buff/peer/self_boost';CLOCK='buff/peer/self_clock'
def package(count=True):
 return {'schemaVersion':2,'manifest':{'id':'package/peer/ch8joint','requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}},{'id':'rule/peer/rate','kind':'rule','contract':'buff.lifetime_rate','implementation':{'type':'expression','expression':'1'}}],'buffs':[{'id':BOOST,'kind':'buff','stacking':{'mode':'refresh','identity':['definition','target']},'modifiers':[{'attribute':'max_hp','layer':'direct_ratio','value':.5},{'attribute':'atk','layer':'direct_ratio','value':.65}]},{'id':CLOCK,'kind':'buff','duration_seconds':4/30,'lifetime':{'rule':'rule/peer/rate','parameters':{},'count_when_inactive':count}}],'entities':[{'id':'unit/peer/boss','kind':'entity','components':{'spatial':{},'attributes':{'base':{'max_hp':50000,'atk':700,'def':37,'mres':17}},'resources':{'hp':{'initial':50000,'capacity_attribute':'max_hp','role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'},'rebirth':{'resource':'hp','max_count':1,'delay_seconds':5/30,'restore_ratio':.5,'restore_rule':'rule/peer/restore','retain_buffs':[BOOST,CLOCK],'on_begin':[{'op':'apply_buff','target':'self','buff':BOOST},{'op':'apply_buff','target':'self','buff':CLOCK}]}}},{'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/kill','ability/peer/cancel','ability/peer/foreign']}}],'abilities':[{'id':'ability/peer/kill','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'instant_kill','target':2,'parameters':{'cause':'peer_joint','skip_rebirth':False}}]},'timeline':[]},{'id':'ability/peer/cancel','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]},'timeline':[]},{'id':'ability/peer/foreign','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'apply_buff','target':2,'buff':BOOST}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/ch8joint','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':2},'initialEntities':[{'definition':'unit/peer/boss','instanceAlias':'boss','position':{'row':0,'col':0}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':1}}]}}
def make(p=None,registry=None):
 p=p or package();INPUTS.append(deepcopy(p));reg=registry or BUILTIN_PROVIDERS;return Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=8850000)
def command(s,name,at):s.submit({'action':'skill','source':'director','ability':'ability/peer/'+name},at=at)
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def proof(s,tmp_path,split,end,reg=None):
 reg=reg or BUILTIN_PROVIDERS;s.advance(split);pin=write_ordered(tmp_path/'joint.cp.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'joint.cp.json',pin),providers=reg);s.advance(end-split);r.advance(end-split);h=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==h.checkpoint();return s
def row(s,definition):return next(b for b in s.ctx.get('boss',('buffs','instances')) if b['definition']==definition)
@pytest.mark.parametrize('count,expiry',[(True,5),(False,10)])
def test_actual_selflease_inactive_dynamic_clock_and_first_restore_full_boost(count,expiry,tmp_path):
 s=make(package(count));command(s,'kill',1);s.advance(3);assert not s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==0 and retained(s.ctx,row(s,BOOST)) and retained(s.ctx,row(s,CLOCK))
 attrs=pure_attributes(s.ctx,2);assert attrs['max_hp']==75000 and attrs['atk']==1155;pin=write_ordered(tmp_path/'waiting3.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'waiting3.json',pin));s.advance(9);r.advance(9);h=replay(s.program,s.export_replay());capture(s,'count_'+str(count));assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 assert s.ctx.active('boss') and s.ctx.resources.current('boss','hp')==37500 and pure_attributes(s.ctx,2)['max_hp']==75000 and pure_attributes(s.ctx,2)['atk']==1155
 assert [e['time'] for e in s.session.events if e['type']=='buff.removed' and e['payload']['buff']==CLOCK]==[expiry]
 assert len([e for e in s.session.events if e['type']=='entity.rebirth.completed'])==1
def test_public_foreign_application_rejected_while_lease_owner_HP0_does_not_refresh(tmp_path):
 s=make();command(s,'kill',1);command(s,'foreign',3);proof(s,tmp_path,2,8);capture(s,'foreign');assert len([e for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==BOOST])==1 and row(s,BOOST)['generation']==1 and s.ctx.resources.current('boss','hp')==37500
def test_manual_same_or_foreign_refresh_cannot_borrow_internal_begin_callback():
 s=make();command(s,'kill',1);s.advance(3);before=s.checkpoint()
 for source in ('boss','director'):
  with pytest.raises(ValueError,match='internal begin callback'):s.ctx.buffs.apply(source,'boss',BOOST)
  assert s.checkpoint()==before
 capture(s,'manual_refresh')
@pytest.mark.parametrize('field',['buff_generation','rebirth_generation','incarnation'])
def test_copied_lease_boolean_or_old_generation_has_no_retained_permission(field):
 s=make();command(s,'kill',1);s.advance(3);original=row(s,BOOST);copy=deepcopy(thaw(original))
 if field=='incarnation':copy['rebirth_self_lease']['incarnation']['life']=True
 else:copy['rebirth_self_lease'][field]=True
 assert retained(s.ctx,original) and not retained(s.ctx,copy);capture(s,'typed_'+field)
 stale=deepcopy(thaw(original));stale['rebirth_self_lease']['rebirth_generation']+=1;assert not retained(s.ctx,stale)
def test_public_withdraw_cancels_finish_clock_and_source_self_privilege(tmp_path):
 s=make(package(False));command(s,'kill',1);command(s,'cancel',3);proof(s,tmp_path,2,13);capture(s,'cancel');assert not s.ctx.active('boss') and not s.ctx.alive('boss') and s.ctx.resources.current('boss','hp')==0
 assert not any(e['type']=='entity.rebirth.completed' for e in s.session.events) and not s.ctx.get('boss',('buffs','instances'))
 assert not [t for t in s.session.scheduler.pending if t['kind'] in ('domain.rebirth.finish','domain.buff.lifetime')]
def test_expiry_self_clock_on_remove_latefault_rolls_back_world_and_leaves_finish_scope_clear():
 p=package();p['buffs'][1]['on_remove']=[{'op':'emit','event':'peer.clock.before_fault'},{'op':'modify_resource','target':3,'resource':'absent','amount':1}];s=make(p);command(s,'kill',1);s.advance(5);before=s.checkpoint()
 with pytest.raises(Exception):s.advance(1)
 after=s.checkpoint();capture(s,'expiry_fault');assert before['kernel']['world']==after['kernel']['world'] and before['kernel']['events']==after['kernel']['events'] and before['kernel']['random']==after['kernel']['random']
 assert not getattr(s.ctx.rebirth,'_self_buff_finishing',[]) and s.session.current_task is None
def reuse_package():
 p=package(False);p['scenarioDraft']['map']={'rows':1,'cols':4};item=p['scenarioDraft']['initialEntities'][0];item.pop('instanceAlias');item.update(active=False,registration_key='peer_boss',reactivation={'max_activations':2,'after_reasons':['withdrawn']});p['scenarioDraft']['initialEntities'].append({'definition':'unit/peer/recipient','instanceAlias':'recipient','position':{'row':0,'col':3}})
 p['entities'].append({'id':'unit/peer/recipient','kind':'entity','tags':['recipient'],'components':{'spatial':{},'attributes':{'base':{'max_hp':10000,'atk':0,'def':13,'mres':17}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'lifecycle':{'policy':'policy/ark_lifecycle'}}});p['buffs'].append({'id':'buff/peer/new_atk','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':300}]})
 p['entities'][0]['components']['abilities']=['ability/peer/fire'];p['selectors']=[{'id':'selector/peer/recipient','kind':'selector','region':{'type':'all'},'filters':[{'tag':'recipient'}],'limit':1}];p['rules']+=[{'id':'rule/peer/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},{'id':'rule/peer/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}]
 p['projectiles']=[{'id':'projectile/peer/old','kind':'projectile','motion':{'rule':'rule/peer/motion','parameters':{'mode':'homing','speed':3}},'collision':{'rule':'rule/peer/collision','parameters':{'enabled':False}},'lifetime_seconds':5,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}]
 p['abilities'] += [{'id':'ability/peer/fire','kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/recipient','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':1,'read_mode':{'source_attributes':'at_launch','target_attributes':'at_hit'},'projectile_definition':'projectile/peer/old'}}]}]
 for name,effects in [('activate',[{'op':'activate_predefined','target':'battle','parameters':{'key':'peer_boss'}}]),('fire_old',[{'op':'trigger_ability','target':2,'ability':'ability/peer/fire'}]),('bonus_new',[{'op':'apply_buff','target':5,'buff':'buff/peer/new_atk'}])]:
  p['entities'][1]['components']['abilities'].append('ability/peer/'+name);p['abilities'].append({'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':'manual','on_start':effects},'timeline':[]})
 return p
def test_reused_predefined_fresh_actor_has_no_old_selflease_or_clock_and_old_projectile_keeps_old_source(tmp_path):
 s=make(reuse_package())
 for name,at in [('activate',0),('fire_old',1),('kill',2),('cancel',3),('activate',4),('bonus_new',5)]:command(s,name,at)
 proof(s,tmp_path,3,60);capture(s,'reuse_projectile');old=2;new=s.ctx.state()['predefined_registry']['peer_boss'];assert new==5 and not s.ctx.alive(old) and s.ctx.alive(new)
 assert s.ctx.resources.current(new,'hp')==50000 and pure_attributes(s.ctx,new)['max_hp']==50000 and pure_attributes(s.ctx,new)['atk']==1000
 assert not any(b['definition'] in (BOOST,CLOCK) for b in s.ctx.get(new,('buffs','instances'),[])) and not s.ctx.get(new,('runtime','rebirth','self_buff_leases'),{})
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==1 and hits[0]['payload']['source']==old and hits[0]['payload']['target']==4 and hits[0]['payload']['amount']==687 and s.ctx.resources.current('recipient','hp')==9313
def test_reuse_budget_rejection_preserves_fresh_incarnation_and_source_state(tmp_path):
 s=make(reuse_package())
 for name,at in [('activate',0),('kill',1),('cancel',2),('activate',3),('activate',4)]:command(s,name,at)
 proof(s,tmp_path,3,10);capture(s,'reuse_budget');assert s.ctx.state()['predefined_reactivation']['peer_boss']['activations']==2 and s.ctx.state()['predefined_registry']['peer_boss']==5
 assert len([e for e in s.session.events if e['type']=='command.rejected'])==1 and s.ctx.resources.current(5,'hp')==50000

