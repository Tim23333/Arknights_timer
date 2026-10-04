from copy import deepcopy
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture(order='higher_first'):
 ids=['ability/peer/fallback','ability/peer/normal','ability/peer/high'];abilities=[]
 for name,mode in [('normal','automatic_attack'),('high','manual'),('fallback','manual')]:
  abilities.append({'id':'ability/peer/'+name,'kind':'ability','activation':{'mode':mode,'parameters':{'blocks_attacks':True}},'cooldown_seconds':3,'timeline':[{'at':7,'effect':{'op':'emit','event':'peer.'+name}}]})
 spec={'priority_order':order,'busy':'all_casts','entries':[{'ability':'ability/peer/'+name,'priority':prio,'attack_clock':True,'require_attack_control':True,'condition':'True','parameters':{}} for name,prio in [('normal',0),('high',10),('fallback',5)]]}
 actor={'id':'unit/peer','kind':'entity','tags':['enemy'],'components':{'abilities':ids,'ability_arbitration':spec,'attributes':{'base':{'max_hp':300,'attack_interval':1,'attack_speed_ratio':1}},'resources':{'hp':{'initial':300,'capacity':300,'role':'health'},'sp':{'initial':5,'capacity':5}},'lifecycle':{'policy':'policy/ark_lifecycle'}}}
 return {'manifest':{'requires':['preset/ark_standard']},'definitions':[actor,*abilities],'scenarioDraft':{'id':'scene/peer/arbitration','ruleset':'ruleset/ark_standard','map':{'rows':2,'cols':2},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':99999,'capacity':99999}},'initialEntities':[{'definition':'unit/peer','instanceAlias':'actor','position':{'row':0,'col':0}}]}}
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=97531)
def ev(s,t):return [thaw(e) for e in s.session.events if e['type']==t]
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot()})
@pytest.mark.parametrize('order,expected',[('higher_first','high'),('lower_first','normal')])
def test_three_abilities_shuffled_array_priority_independent_and_declared_clock(order,expected,tmp_path):
 s=make(fixture(order));s.advance(1);assert ev(s,'ability.started')[0]['payload']['ability']=='ability/peer/'+expected;assert s.ctx.get('actor',('runtime','next_attack'))==30
 pin=write_ordered(tmp_path/'active.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'active.json',pin));s.advance(30);r.advance(30)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'shuffled_'+order)
def test_failed_higher_cost_and_empty_target_rollback_then_valid_fallback():
 p=fixture();high=next(a for a in p['definitions'] if a['id']=='ability/peer/high');high['activation']['costs']=[{'resource':'sp','amount':6}]
 s=make(p);s.advance(1);capture(s,'unpayable_high');assert ev(s,'ability.started')[0]['payload']['ability']=='ability/peer/fallback';assert s.ctx.resources.current('actor','sp')==5
 p=fixture();high=next(a for a in p['definitions'] if a['id']=='ability/peer/high');high['selector']='selector/peer/empty';high['activation']['parameters']['requires_targets']=True
 p['definitions'].append({'id':'selector/peer/empty','kind':'selector','region':{'type':'all'},'filters':[{'tag':'absent'}],'limit':1});s=make(p);s.advance(1);capture(s,'targetless_high');assert ev(s,'ability.started')[0]['payload']['ability']=='ability/peer/fallback'
def test_fatal_started_random_effect_failure_restores_entire_attempt_before_fallback():
 p=fixture();high=next(a for a in p['definitions'] if a['id']=='ability/peer/high');high['activation']['costs']=[{'resource':'sp','amount':2}];high['activation']['on_start']=[{'op':'random','stream':'peer_arbiter_fault','on_success':[{'op':'modify_resource','resource':'missing','delta':1}]}]
 s=make(p);before=s.checkpoint();from ark_sim.domains.ability_arbitration import tick
 with pytest.raises(ValueError):tick(s.ctx.abilities,s.session.world.resolve('actor'))
 assert s.checkpoint()==before;assert not ev(s,'ability.arbitrated');capture(s,'fatal_no_fallback_atomic')
def test_public_started_reaction_retires_source_after_committed_clock_preserving_cost(tmp_path):
 p=fixture();high=next(a for a in p['definitions'] if a['id']=='ability/peer/high');high['activation']['costs']=[{'resource':'sp','amount':2}];high['events']=[{'event':'ability.started','condition':'inputs.payload.source == 2','effects':[{'op':'schedule','target':2,'delay_seconds':0,'effect':{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}}]}]
 s=make(p);s.advance(1);assert not s.ctx.active('actor') and s.ctx.get('actor',('runtime','next_attack'))==30 and s.ctx.resources.current('actor','sp')==3
 assert s.ctx.get('actor',('runtime','casts'))=={};pin=write_ordered(tmp_path/'retired.json',s.checkpoint());r=Engine.restore(s.program,load_bound(tmp_path/'retired.json',pin));s.advance(40);r.advance(40)
 assert s.checkpoint()==r.checkpoint() and s.snapshot()==replay(s.program,s.export_replay()).snapshot();capture(s,'accepted_then_retired');assert len(ev(s,'ability.started'))==1 and not ev(s,'peer.high')
def test_replaceable_half_interval_rule_sets15_and_source_initial_delay_skips_high():
 p=fixture();p['rules']=[{'id':'rule/peer/interval','kind':'rule','contract':'time.interval','implementation':{'type':'expression','expression':'inputs.base_interval / 2'}}];p['scenarioDraft']['rules']={'time.interval':'rule/peer/interval'}
 next(a for a in p['definitions'] if a['id']=='ability/peer/high')['initial_cooldown_seconds']=2
 s=make(p);s.advance(1);capture(s,'interval_substitution');assert ev(s,'ability.started')[0]['payload']['ability']=='ability/peer/fallback';assert s.ctx.get('actor',('runtime','next_attack'))==15 and s.ctx.get('actor',('runtime','cooldowns','ability/peer/high'))==60
@pytest.mark.parametrize('dormant',[False,True])
def test_unpossessed_effective_override_never_allocates_partial_actor(dormant):
 s=make(fixture());spec=deepcopy(fixture()['definitions'][0]['components']['ability_arbitration']);spec['entries'][0]['ability']='ability/peer/unowned';before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.create('unit/peer',alias='bad',active=not dormant,registration_key='bad' if dormant else None,component_overrides={'ability_arbitration':spec})
 assert s.checkpoint()==before;capture(s,'bad_override_'+str(dormant))
def test_non_boolean_condition_is_fatal_without_cast_payment_clock_or_rng():
 p=fixture();p['definitions'][0]['components']['ability_arbitration']['entries'][1]['condition']='1';s=make(p);before=s.checkpoint();from ark_sim.domains.ability_arbitration import tick
 with pytest.raises(ValueError,match='strict boolean'):tick(s.ctx.abilities,s.session.world.resolve('actor'))
 assert s.checkpoint()==before;capture(s,'condition_strict')
