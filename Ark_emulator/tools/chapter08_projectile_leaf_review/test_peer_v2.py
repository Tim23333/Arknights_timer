from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.kernel.world import World
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def package():
 return {'schemaVersion':2,'manifest':{'id':'package/peer/projectile_leaf','requires':['preset/ark_standard']},'buffs':[{'id':'buff/peer/atk','kind':'buff','modifiers':[{'attribute':'atk','layer':'flat','value':200}]}],'rules':[{'id':'rule/peer/motion','kind':'rule','contract':'projectile.trajectory','implementation':{'type':'provider','provider':'model.projectile.trajectory'}},{'id':'rule/peer/collision','kind':'rule','contract':'projectile.collision','implementation':{'type':'provider','provider':'model.projectile.collision'}}],'projectiles':[{'id':'projectile/peer/flight','kind':'projectile','motion':{'rule':'rule/peer/motion','parameters':{'mode':'homing','speed':2.3}},'collision':{'rule':'rule/peer/collision','parameters':{'enabled':False}},'lifetime_seconds':5,'max_hits':1,'can_hit_same_target':False,'stop_after_max':True,'stop_after_first':False,'attach_at_launch':False,'lifecycle':{'source_invalid':'retain','source_hidden':'retain','target_invalid':'retain_position','target_hidden':'retain_position','finish_on_reach':True,'hit_on_reach':True,'force_reach_on_expire':True,'hit_on_expire':True}}],'entities':[{'id':'unit/peer/source','kind':'entity','components':{'attributes':{'base':{'max_hp':9000,'atk':421,'def':31,'mres':17}},'resources':{'hp':{'initial':9000,'capacity':9000,'role':'health'}},'spatial':{},'buffs':{'initial':['buff/peer/atk']},'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/peer/physical','ability/peer/arts']}},{'id':'unit/peer/target','kind':'entity','tags':['recipient'],'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':137,'mres':23}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},{'id':'unit/peer/director','kind':'entity','components':{'spatial':{},'abilities':['ability/peer/retire']}}],'selectors':[{'id':'selector/peer/recipient','kind':'selector','region':{'type':'all'},'filters':[{'tag':'recipient'}],'limit':1}],'abilities':[{'id':'ability/peer/'+dtype,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/recipient','timeline':[{'at':0,'effect':{'op':'damage','damage_type':dtype,'scale':1,'projectile_definition':'projectile/peer/flight','read_mode':{'source_attributes':'at_hit','target_attributes':'at_hit'}}}]} for dtype in ('physical','arts')]+[{'id':'ability/peer/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]},'timeline':[]}],'scenarioDraft':{'id':'scene/peer/leaf','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':4},'initialEntities':[{'definition':'unit/peer/source','instanceAlias':'source','position':{'row':0,'col':0}},{'definition':'unit/peer/target','instanceAlias':'target','position':{'row':0,'col':3}},{'definition':'unit/peer/director','instanceAlias':'director','position':{'row':0,'col':1}}]}}
def make():p=package();INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=88421)
def capture(s,name):CAPTURES.append({'case':name,'checkpoint':s.checkpoint(),'snapshot':s.snapshot(),'events':thaw(tuple(s.session.events)),'replay':s.export_replay()})
def test_retired_source_live_hit_ATK_not_launch_buff_and_two_inflight_CP_head(tmp_path):
 s=make();s.submit({'action':'skill','source':'source','ability':'ability/peer/physical'},at=0);s.submit({'action':'skill','source':'source','ability':'ability/peer/arts'},at=1);s.submit({'action':'skill','source':'director','ability':'ability/peer/retire'},at=4);s.advance(20);pin=write_ordered(tmp_path/'leaf20.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'leaf20.json',pin));s.advance(40);r.advance(40);h=replay(s.program,s.export_replay());capture(s,'retired_flight');assert s.checkpoint()==r.checkpoint()==h.checkpoint()
 hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert len(hits)==2 and all(e['payload']['source']==2 for e in hits) and [e['payload']['amount'] for e in hits]==[284,421*(1-23/100)]
 assert s.ctx.resources.current('target','hp')==10000-284-421*(1-23/100) and not s.ctx.active('source')
def test_leaf_put_single_world_version_order_and_old_cached_view_is_stable():
 s=make();s.ctx.set('system/battle',('projectiles',),{'next_id':9,'instances':{'z':{'id':'z','value':7},'a':{'id':'a','value':1},'m':{'id':'m','value':3}}});w=s.session.world;old=w.get('system/battle');version=w.version('system/battle');before=s.ctx.projectiles._get('a');s.ctx.projectiles._put({'id':'a','value':11});assert w.version('system/battle')==version+1 and list(s.ctx.projectiles._state()['instances'])==['z','a','m'] and before['value']==1 and old['components']['projectiles']['instances']['a']['value']==1
 s.ctx.projectiles._put({'id':'new','value':4});assert list(s.ctx.projectiles._state()['instances'])==['z','a','m','new'];capture(s,'put_order')
def test_leaf_put_transaction_latefault_restores_all_stores_and_unaffected_sibling():
 s=make();s.ctx.set('system/battle',('projectiles',),{'next_id':9,'instances':{'a':{'id':'a','value':1},'b':{'id':'b','value':2}}});before=s.checkpoint()
 with pytest.raises(ValueError):
  with s.session.atomic():
   s.ctx.projectiles._put({'id':'a','value':99});s.session.random.sample('peer.leaf.fault');s.ctx.emit('peer.leaf.before_fault',{});s.session.schedule('domain.projectile.step',{'id':'a'},3);raise ValueError('peer leaf latefault')
 capture(s,'put_fault');assert s.checkpoint()==before and s.ctx.projectiles._get('b')['value']==2 and s.ctx.projectiles._get('missing') is None
def test_component_subtree_deep_readonly_default_mapping_only_unknown_identity_and_views():
 w=World();ref=w.create('unit/peer/view',{'tree':{'ordered':{'z':1,'a':2},'nested':[{'v':3}]},'other':{'value':7}},alias='view');before=w.get(ref);version=w.version(ref)
 if not hasattr(w,'component_view'):return
 view=w.component_view('view',('tree',));assert w.get(ref) is before and w.version(ref)==version
 with pytest.raises(TypeError):view['ordered']['z']=99
 with pytest.raises(TypeError):view['nested'][0]['v']=99
 marker={'caller':17};assert w.component_view(ref,('missing',),marker) is marker and w.component_view(ref,('tree','nested',0),marker) is marker
 with pytest.raises(KeyError):w.component_view('unknown',('tree',))
 w.set(ref,('tree','ordered','z'),9);assert view['ordered']['z']==1 and before['components']['tree']['ordered']['z']==1 and w.component_view(ref,('tree','ordered','z'))==9 and w.version(ref)==version+1
 CAPTURES.append({'case':'view','world':w.snapshot(),'old':thaw(before),'leaf':thaw(view)})

