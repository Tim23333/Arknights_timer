"""Independent literal expectations for None-source PUREBUFF and real timer leases."""
import json,sys
from copy import deepcopy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];CAND=ROOT.parent/'unpack_work/campaign_content_base_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/content_base_peer_v2'
def effect(bypass=False,amount=30):return {'op':'no_source_damage','fixed_amount':amount,'damage_type':'true','attack_type':'BUFF','damage_without_modify':bypass,'origin':{'source_fixture':'independent/literal30'},'ignore_for_sp':True,'node_is_env_damage':False,'env_blackboard_injected':False,'environmental':False,'rules':{'damage.pipeline':'rule/peer/pipeline'}}
def package(hook='quarter',bypass=False,enemy=False):
 p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},'rules':[{'id':'rule/peer/pipeline','kind':'rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':"{'accepted':True,'amount':inputs.effect.fixed_amount*2,'allocations':[],'events':[]}"}},{'id':'rule/peer/hook','kind':'rule','contract':'damage.pipeline','implementation':{'type':'expression','expression':"{'accepted':True,'amount':inputs.effect.settlement.amount*.25,'allocations':[],'events':[]}" if hook=='quarter' else "{'accepted':False,'amount':0,'allocations':[],'events':[]}"}}],'buffs':[{'id':'buff/peer/hook','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/peer/hook',**({'samples':{'stream':'peer/dodge','count':1}} if hook=='dodge' else {})}]}],'entities':[{'id':'unit/peer/target','kind':'entity','tags':['enemy' if enemy else 'player','ground'],'components':{'attributes':{'base':{'max_hp':100,'atk':0,'def':9000,'mres':99}},'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'selection_state':{'side':1 if enemy else 0,'motion':1,'category':1,'unit_type':2 if enemy else 1},'spatial':{},'buffs':{'initial':['buff/peer/hook']},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],'scenarioDraft':{'id':'scene/peer/none','ruleset':'ruleset/ark_standard','seed':913,'map':{'rows':1,'cols':2},'objectives':{},'initialEntities':[{'definition':'unit/peer/target','instanceAlias':'victim','position':{'row':0,'col':0}}],'dependencies':['rule/peer/pipeline']}}
 return p
def compile_package(p):
 p=deepcopy(p)
 for rule in p['rules']:
  impl=rule['implementation']
  if impl['type']=='expression' and rule['contract']=='damage.pipeline':rule['implementation']={'type':'graph','nodes':[{'id':'result','expression':impl['expression']}],'output':'nodes.result'}
 return Compiler().compile(p)
def rows(s,t):return [e for e in s.snapshot()['events'] if e['type']==t]
@pytest.mark.parametrize('bypass,expected',[(False,15),(True,30)])
def test_NoneSource_BUFF_true_without_modify_policy_preserves_or_skips_pipeline_hook(bypass,expected):
 s=Engine.create(compile_package(package()));s.ctx.effects.execute(None,[s.session.world.resolve('victim')],effect(bypass));assert s.ctx.resources.current('victim','hp')==100-expected;e=rows(s,'damage.accepted')[-1];assert e['payload']['amount']==expected and e['payload']['source'] is None and e['payload']['attack_type']=='BUFF';assert bool(rows(s,'damage.modification_bypassed')) is bypass
@pytest.mark.parametrize('bypass,damage,samples',[(False,0,1),(True,30,0)])
def test_target_dodge_rng_only_modified_path(bypass,damage,samples):
 s=Engine.create(compile_package(package('dodge')));before=s.session.random.snapshot();s.ctx.effects.execute(None,[s.session.world.resolve('victim')],effect(bypass));assert s.ctx.resources.current('victim','hp')==100-damage;after=s.session.random.snapshot();assert len(after['samples'])-len(before['samples'])==samples
def test_bypass_true_bounds_lethal_claim_and_none_attribution():
 s=Engine.create(compile_package(package(enemy=True)));s.ctx.effects.execute(None,[s.session.world.resolve('victim')],effect(True,500));assert s.ctx.resources.current('victim','hp')==0 and not s.ctx.alive('victim');e=rows(s,'damage.accepted')[-1];assert e['payload']['amount']==100 and e['payload']['pipeline_amount']==500 and e['payload']['source'] is None;assert s.ctx.state()['kills']==1;assert rows(s,'entity.died')[-1]['payload']['source'] is None
def test_target_hook_bad_late_allocation_rolls_full_packet_resources_trace_rng():
 p=package('dodge');p['rules'][1]['implementation']['expression']="{'accepted':True,'amount':30,'allocations':[{'target':'target','resource':'hp','amount':20},{'target':'target','resource':'hp','amount':-1}],'events':[]}";s=Engine.create(compile_package(p));before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute(None,[s.session.world.resolve('victim')],effect(False))
 assert s.checkpoint()==before
def test_owned_timer_refresh_remove_origin_generation_CP_head():
 p=package();p['entities'][0]['components']['buffs']['initial']=[];p['buffs'].append({'id':'buff/peer/timer','kind':'buff','interval_seconds':2/30,'duration_seconds':9/30,'effects':[effect(True,10)]});p['selectors']=[{'id':'selector/peer/victim','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'}]}];p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'apply_buff','buff':'buff/peer/timer','selector':'selector/peer/victim'}},{'at':3,'effect':{'op':'apply_buff','buff':'buff/peer/timer','selector':'selector/peer/victim'}},{'at':8,'effect':{'op':'remove_buff','buff':'buff/peer/timer','selector':'selector/peer/victim'}}];program=compile_package(p);s=Engine.create(program);s.session.advance(4);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'owned_timer4.cp.json';assert not cp.exists();h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.session.advance(8);r.session.advance(8);assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot();hits=rows(s,'damage.accepted');assert [e['time'] for e in hits]==[2,5,7] and s.ctx.resources.current('victim','hp')==70;assert [e['payload']['origin']['buff_timer']['generation'] for e in hits]==[1,2,2];assert all(e['payload']['source'] is None and e['payload']['origin']['buff_timer']['owner']==s.session.world.resolve('victim') for e in hits);assert not s.ctx.entity('victim')['components']['buffs']['instances'];(OUT/'owned_timer_actual.json').write_text(json.dumps({'input':p,'cp_sha':h,'snapshot':s.snapshot()},indent=2)+'\n',encoding='utf8',newline='')
def test_owner_dead_after_first_periodic_packet_no_more_lease_damage():
 p=package();p['entities'][0]['components']['buffs']['initial']=[];p['buffs'].append({'id':'buff/peer/lethal_timer','kind':'buff','interval_seconds':2/30,'effects':[effect(True,500)]});p['entities'][0]['components']['buffs']['initial']=['buff/peer/lethal_timer'];s=Engine.create(compile_package(p));s.session.advance(10);assert len(rows(s,'damage.accepted'))==1 and not s.ctx.alive('victim')

def test_source_timer_owner_applicability_changes_before_NoSource_skips_actual_packet():
 p=package();p['rules'].append({'id':'rule/peer/active','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'inputs.owner.components.resources.hp.current > 50'}});p['buffs'].append({'id':'buff/peer/inactive_timer','kind':'buff','interval_seconds':2/30,'active_rule':'rule/peer/active','effects':[{'op':'modify_resource','resource':'hp','value':40},effect(True,10)]});p['entities'][0]['components']['buffs']['initial']=['buff/peer/inactive_timer'];s=Engine.create(compile_package(p));s.session.advance(8);assert s.ctx.resources.current('victim','hp')==40 and not rows(s,'damage.accepted')
def test_periodic_source_instance_removal_before_NoSource_does_not_borrow_old_lease():
 p=package();p['buffs'].append({'id':'buff/peer/self_remove','kind':'buff','interval_seconds':2/30,'effects':[{'op':'remove_buff','buff':'buff/peer/self_remove'},effect(True,10)]});p['entities'][0]['components']['buffs']['initial']=['buff/peer/self_remove'];s=Engine.create(compile_package(p));s.session.advance(8);assert s.ctx.resources.current('victim','hp')==100 and not rows(s,'damage.accepted') and not s.ctx.entity('victim')['components']['buffs']['instances']
@pytest.mark.parametrize('field,value',[('damage_without_modify',1),('fixed_amount',True),('fixed_amount',float('nan')),('ignore_for_sp',0),('attack_type','NORMAL')])
def test_NoneSource_request_strict_types_leave_all_stores(field,value):
 s=Engine.create(compile_package(package()));request=effect();request[field]=value;before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.effects.execute(None,[s.session.world.resolve('victim')],request)
 assert s.checkpoint()==before

def test_modified_allocation_keeps_real_hp_and_secondary_resource_bounds():
 p=package(enemy=True);p['entities'][0]['components']['resources']['sp']={'initial':2,'capacity':3};p['rules'][0]['implementation']['expression']="{'accepted':True,'amount':200,'allocations':[{'target':'target','resource':'hp','amount':200},{'target':'target','resource':'sp','amount':5}],'events':[]}";p['rules'][1]['implementation']['expression']='inputs.effect.settlement';s=Engine.create(compile_package(p));s.ctx.effects.execute(None,[s.session.world.resolve('victim')],effect(False));assert s.ctx.resources.current('victim','hp')==0 and s.ctx.resources.current('victim','sp')==0 and s.ctx.state()['kills']==1;event=rows(s,'damage.accepted')[-1];assert event['payload']['amount']==100 and event['payload']['total_health_loss']==100;assert [r['actual_delta'] for r in event['payload']['allocations']]==[-100,-2]
