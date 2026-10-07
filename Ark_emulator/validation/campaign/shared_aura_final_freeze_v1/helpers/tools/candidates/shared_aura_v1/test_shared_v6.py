"""Two actual live parents, one unchanged nonstacking source marker/attribute child."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_shared_aura_v5_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
MARKER='buff/ch7/source/enemy_9D0_talent_strength';OUT=ROOT/'validation/campaign/shared_aura_author_v6'
POLICY={'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject'}
def package():
 marker=next(b for b in json.loads((ROOT/'packages/campaign/chapter07_strength_melee/module.enemy_1078_sotisc.v5.json').read_bytes())['buffs'] if b['id']==MARKER);p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'buffs':[marker,{'id':'buff/peer/attributes','kind':'buff','modifiers':[{'attribute':'atk','layer':'direct_ratio','value':.2},{'attribute':'def','layer':'flat','value':200}]}],'selectors':[{'id':'selector/peer/receiver','kind':'selector','region':{'type':'all'},'filters':[{'tag':'receiver'}]}],'entities':[]}
 for name in ('parent1','parent2','receiver'):
  components={'attributes':{'base':{'atk':100,'def':50,'max_hp':100}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},'lifecycle':{'policy':'policy/ark_lifecycle'}}
  if name!='receiver':
   ids=[]
   for suffix,child in (('marker',MARKER),('attributes','buff/peer/attributes')):
    bid='buff/peer/'+name+'/'+suffix;ids.append(bid);p['buffs'].append({'id':bid,'kind':'buff','aura':{'selector':'selector/peer/receiver','buff':child,'lease_policy':deepcopy(POLICY)}})
   components['buffs']={'initial':ids}
  p['entities'].append({'id':'unit/peer/'+name,'kind':'entity','tags':[name],'components':components})
 p['scenarioDraft']={'id':'scene/peer/shared_aura','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'objectives':{},'dependencies':[b['id'] for b in p['buffs']],'initialEntities':[{'definition':'unit/peer/'+name,'instanceAlias':name,'position':{'row':0,'col':i}} for i,name in enumerate(('parent1','parent2','receiver'))]};return p
def children(s):return [i for i in s.ctx.entity('receiver')['components']['buffs']['instances'] if i['definition'] in (MARKER,'buff/peer/attributes')]
def test_two_parents_one_child_nonstacking_then_remove_first_and_last():
 s=Engine.create(Compiler().compile(package()));items=children(s);assert len(items)==2 and all(i['stacks']==1 and len(i['aura_leases'])==2 for i in items);assert s.ctx.attributes.value('receiver','atk')==120 and s.ctx.attributes.value('receiver','def')==250;ids=[i['id'] for i in items];s.ctx.lifecycle.retire('parent1','withdrawn');items=children(s);assert [i['id'] for i in items]==ids and all(len(i['aura_leases'])==1 and i['source']==s.session.world.resolve('parent2') for i in items);assert s.ctx.attributes.value('receiver','atk')==120;s.ctx.lifecycle.retire('parent2','withdrawn');assert not children(s) and s.ctx.attributes.value('receiver','atk')==100 and s.ctx.attributes.value('receiver','def')==50
def test_external_same_id_apply_while_leased_rolls_all_stores():
 s=Engine.create(Compiler().compile(package()));before=s.checkpoint()
 with pytest.raises(ValueError,match='External application'):s.ctx.buffs.apply('parent2','receiver',MARKER)
 assert s.checkpoint()==before
def test_actual_two_parent_public_remove_CP_head_exact_lease_rows():
 p=package();p['selectors'] += [{'id':'selector/peer/p1','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent1'}]},{'id':'selector/peer/p2','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent2'}]}];p['scenarioDraft']['scheduledEffects']=[{'at':8,'effect':{'op':'retire','selector':'selector/peer/p1','parameters':{'reason':'withdrawn'}}},{'at':15,'effect':{'op':'retire','selector':'selector/peer/p2','parameters':{'reason':'withdrawn'}}}];program=Compiler().compile(p);s=Engine.create(program);s.session.advance(5);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'actual5.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.session.advance(14);r.session.advance(14);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();assert not children(s);(OUT/'public_actual.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')

def test_late_second_parent_same_source_does_not_refresh_child():
 p=package();p['entities'][1]['components']['buffs']['initial']=[];s=Engine.create(Compiler().compile(p));before=[(i['id'],i['generation'],i['started_at']) for i in children(s)];s.session.advance(4)
 for suffix in ('marker','attributes'):s.ctx.buffs.apply('parent1','parent2','buff/peer/parent2/'+suffix)
 assert [(i['id'],i['generation'],i['started_at']) for i in children(s)]==before and all(len(i['aura_leases'])==2 and i['source']==s.session.world.resolve('parent1') for i in children(s));assert s.ctx.attributes.value('receiver','atk')==120
def test_real_parent_refresh_rebinds_source_without_refreshing_shared_child():
 p=package()
 for b in p['buffs']:
  if b['id'].startswith('buff/peer/parent1/'):b['stacking']={'mode':'refresh','identity':['definition','target'],'max_stacks':1}
 s=Engine.create(Compiler().compile(p));before=[(i['id'],i['generation'],i['started_at']) for i in children(s)]
 for suffix in ('marker','attributes'):s.ctx.buffs.apply('parent2','parent1','buff/peer/parent1/'+suffix)
 assert [(i['id'],i['generation'],i['started_at']) for i in children(s)]==before and all(i['source']==s.session.world.resolve('parent2') for i in children(s));assert all(any(l['center']==s.session.world.resolve('parent1') and l['parent_generation']==2 for l in i['aura_leases'].values()) for i in children(s))
def test_true_parent_death_leaves_other_lease_source_and_max1():
 s=Engine.create(Compiler().compile(package()));s.ctx.effects.execute('parent2',[s.session.world.resolve('parent1')],{'op':'damage','damage_type':'true','scale':0,'additions':100});assert not s.ctx.alive('parent1') and all(len(i['aura_leases'])==1 and i['source']==s.session.world.resolve('parent2') for i in children(s));assert s.ctx.attributes.value('receiver','atk')==120
def test_external_child_preexists_acquisition_rejects_full_transaction():
 p=package()
 for d in p['entities'][:2]:d['components']['buffs']['initial']=[]
 s=Engine.create(Compiler().compile(p));s.ctx.buffs.apply('parent2','receiver',MARKER);before=s.checkpoint()
 with pytest.raises(ValueError,match='External same-ID'):s.ctx.buffs.apply('parent1','parent1','buff/peer/parent1/marker')
 assert s.checkpoint()==before
def test_canonical_source_dependent_active_rule_recomputed_after_detach():
 p=package();p['entities'][0]['components']['attributes']['base']['atk']=200;p['rules']=[{'id':'rule/peer/source_active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'inputs.source.components.attributes.base.atk >= 200'}}];p['buffs'][1]['active_rule']='rule/peer/source_active';s=Engine.create(Compiler().compile(p));assert s.ctx.attributes.value('receiver','atk')==120;s.ctx.lifecycle.retire('parent1','withdrawn');assert children(s) and s.ctx.attributes.value('receiver','atk')==100 and all(i['source']==s.session.world.resolve('parent2') for i in children(s))

def test_real_rebirth_same_actor_new_parent_incarnation_only_other_lease_during_wait():
 p=package();p['rules']=[{'id':'rule/peer/rebirth_restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}}];p['entities'][0]['components']['rebirth']={'resource':'hp','max_count':1,'delay_seconds':1,'restore_ratio':1,'restore_rule':'rule/peer/rebirth_restore','on_finish':[{'op':'apply_buff','buff':'buff/peer/parent1/marker'},{'op':'apply_buff','buff':'buff/peer/parent1/attributes'}]};s=Engine.create(Compiler().compile(p));old=[i['id'] for i in children(s)];s.ctx.effects.execute('parent2',[s.session.world.resolve('parent1')],{'op':'damage','damage_type':'true','scale':0,'additions':100});assert s.ctx.alive('parent1') and not s.ctx.active('parent1') and s.ctx.resources.current('parent1','hp')==0;assert all(len(i['aura_leases'])==1 and i['source']==s.session.world.resolve('parent2') for i in children(s));s.session.advance(32);assert s.ctx.active('parent1') and [i['id'] for i in children(s)]==old and all(len(i['aura_leases'])==2 for i in children(s));assert s.ctx.attributes.value('receiver','atk')==120
def test_on_apply_remove_parent_callback_never_installs_ghost_members_or_lease():
 p=package();p['entities'][1]['components']['buffs']['initial']=[];p['selectors'].append({'id':'selector/peer/remove_p1','kind':'selector','region':{'type':'all'},'filters':[{'tag':'parent1'}]});marker=p['buffs'][0];marker['effects']=[{'op':'retire','selector':'selector/peer/remove_p1','parameters':{'reason':'withdrawn'}}];s=Engine.create(Compiler().compile(p));assert not s.ctx.alive('parent1') and not children(s);assert not any(i.get('aura_members') for i in s.ctx.entity('parent1')['components']['buffs']['instances'])
def test_invalid_late_callback_world_event_rng_scheduler_rollback():
 p=package();p['entities'][0]['components']['buffs']['initial']=[];p['entities'][1]['components']['buffs']['initial']=[];p['buffs'][0]['effects']=[{'op':'modify_resource','resource':'missing_resource','delta':1}];s=Engine.create(Compiler().compile(p));before=s.checkpoint()
 with pytest.raises((KeyError,ValueError)):s.ctx.buffs.apply('parent1','parent1','buff/peer/parent1/marker')
 assert s.checkpoint()==before

def waiting_package():
 p=package();p['entities'][1]['components']['buffs']['initial']=[];p['rules']=[{'id':'rule/peer/rebirth_restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}}];ids=p['entities'][0]['components']['buffs']['initial'];p['entities'][0]['components']['rebirth']={'resource':'hp','max_count':1,'delay_seconds':1,'restore_ratio':1,'restore_rule':'rule/peer/rebirth_restore','retain_buffs':ids}
 for b in p['buffs']:
  if b.get('aura'):b['aura']['lease_policy']['owner_activity']='active_or_rebirth_waiting'
 return p
def test_HP0_real_rebirth_waiting_keeps_one_lease_child_and_modifiers_until_return():
 p=waiting_package();s=Engine.create(Compiler().compile(p));ids=[i['id'] for i in children(s)];s.ctx.effects.execute('parent2',[s.session.world.resolve('parent1')],{'op':'damage','damage_type':'true','scale':0,'additions':100});assert s.ctx.resources.current('parent1','hp')==0 and not s.ctx.active('parent1') and s.ctx.alive('parent1');assert [i['id'] for i in children(s)]==ids and s.ctx.attributes.value('receiver','atk')==120 and s.ctx.attributes.value('receiver','def')==250;s.session.advance(12);assert s.ctx.attributes.value('receiver','atk')==120;s.session.advance(20);assert s.ctx.active('parent1') and [i['id'] for i in children(s)]==ids
def test_waiting_permission_does_not_keep_withdrawn_source_or_faked_waiting():
 s=Engine.create(Compiler().compile(waiting_package()));s.ctx.set('parent1',('runtime','active'),False);s.ctx.set('parent1',('runtime','state'),'rebirth');s.ctx.set('parent1',('runtime','rebirth'),{'phase':'waiting','generation':999,'due_at':30,'task':None});s.ctx.resources.adjust('parent1','hp',value=0);s.ctx.buffs.reconcile();assert not children(s)
 s=Engine.create(Compiler().compile(waiting_package()));s.ctx.lifecycle.retire('parent1','withdrawn');assert not children(s)
