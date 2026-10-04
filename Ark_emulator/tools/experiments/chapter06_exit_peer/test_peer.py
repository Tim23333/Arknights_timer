import pytest,math
from copy import deepcopy
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
INPUTS=[];CAPTURES=[]
def fixture(plan=None,route=False):
 actor={'id':'unit/peer/story','kind':'entity','tags':['enemy'],'components':{'attributes':{'base':{'max_hp':95000,'atk':0,'def':0,'mres':0,'move_speed':2,'block_count':0}},'resources':{'hp':{'initial':95000,'capacity':95000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle','leak_loss':1}}}
 rules=[]
 if plan is not None:
  actor['components']['lifecycle'].update(exit_rule='rule/peer/exit',exit_parameters={'source_unharmful':True});rules.append({'id':'rule/peer/exit','kind':'calculation_rule','contract':'lifecycle.exit','implementation':{'type':'expression','expression':repr(plan)}})
 entry={'definition':actor['id'],'instanceAlias':'actor','position':{'row':0,'col':0}}
 if route:entry['route']={'motionMode':0,'startPosition':{'row':0,'col':0},'endPosition':{'row':0,'col':1},'checkpoints':[]}
 return {'schemaVersion':2,'manifest':{'id':'package/peer/exit','requires':['preset/ark_standard']},'entities':[actor],'rules':rules,'scenarioDraft':{'id':'scene/peer/exit','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'parameters':{'deploy_capacity':0},'objectives':{'life_resource':'life'},'resources':{'life':{'initial':5,'capacity':5}},'initialEntities':[entry]}}
def make(p):INPUTS.append(deepcopy(p));return Engine.create(Compiler().compile(p),seed=63041)
def capture(s,label):CAPTURES.append({'case':label,'events':thaw(tuple(s.session.events)),'commands':s.export_replay(),'snapshot':s.snapshot(),'checkpoint':s.checkpoint()})
def test_actual_route_exit_credit_is_not_combat_death_hp_and_ordered_disk_head_preserved(tmp_path):
 p=fixture({'base_life_loss':0,'kills_delta':1,'leaks_delta':0},True);s=make(p);s.advance(5);cp=tmp_path/'exit_before.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,h));s.advance(20);r.advance(20);head=replay(s.program,s.export_replay());capture(s,'true_route')
 assert s.checkpoint()==r.checkpoint()==head.checkpoint() and thaw(tuple(s.session.events))==thaw(tuple(head.session.events))
 assert not s.ctx.active('actor') and s.ctx.resources.current('actor','hp')==95000 and s.ctx.resources.current('system/battle','life')==5
 assert (s.ctx.state()['kills'],s.ctx.state()['leaks'])==(1,0)
 assert len([e for e in s.session.events if e['type']=='entity.exited'])==1 and not [e for e in s.session.events if e['type'] in ['entity.died','combat.kill']]
 before=s.checkpoint();assert s.ctx.lifecycle.exit('actor') is False and s.checkpoint()==before
def test_noopt_classic_exit_keeps_life_loss_one_and_leak_one():
 p=fixture(route=True);s=make(p);s.advance(25);capture(s,'classic_route');assert s.ctx.resources.current('system/battle','life')==4 and (s.ctx.state()['kills'],s.ctx.state()['leaks'])==(0,1)
def test_real_death_does_not_also_claim_exit_credit():
 p=fixture({'base_life_loss':0,'kills_delta':1,'leaks_delta':0});s=make(p);s.ctx.resources.adjust('actor','hp',value=0);before=s.checkpoint();assert s.ctx.lifecycle.exit('actor') is False;assert s.checkpoint()==before;capture(s,'true_death');assert s.ctx.state()['kills']==1 and not [e for e in s.session.events if e['type']=='lifecycle.exit_accounted']
@pytest.mark.parametrize('field,value',[('base_life_loss',True),('base_life_loss',-1),('kills_delta',True),('leaks_delta',False),('kills_delta',2),('leaks_delta',-1)])
def test_invalid_plan_counts_loss_are_atomic(field,value):
 plan={'base_life_loss':0,'kills_delta':1,'leaks_delta':0};plan[field]=value;p=fixture(plan);s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.exit('actor')
 assert s.checkpoint()==before;capture(s,'invalid_'+field+repr(value))
def test_double_credit_rejected_atomically():
 s=make(fixture({'base_life_loss':0,'kills_delta':1,'leaks_delta':1}));before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.exit('actor')
 assert s.checkpoint()==before
@pytest.mark.parametrize('value',[math.nan,math.inf,-math.inf])
def test_nonfinite_loss_plan_validation(value):
 from ark_sim.domains.exit_accounting import validate
 with pytest.raises(ValueError):validate({'base_life_loss':value,'kills_delta':0,'leaks_delta':0})
@pytest.mark.parametrize('kind',['missing','buff','wrong_contract'])
def test_bad_exit_rule_reference_kind_contract_is_rejected_even_before_exit(kind):
 p=fixture({'base_life_loss':0,'kills_delta':1,'leaks_delta':0})
 if kind=='missing':p['rules']=[]
 elif kind=='buff':p['rules']=[];p['buffs']=[{'id':'rule/peer/exit','kind':'buff'}]
 else:p['rules'][0]['contract']='buff.duration';p['rules'][0]['implementation']['expression']='0'
 INPUTS.append(deepcopy(p))
 with pytest.raises(ValueError):Compiler().compile(p)
def test_last_resource_bounds_rejection_rolls_back_claim_credit_and_events():
 p=fixture({'base_life_loss':1,'kills_delta':1,'leaks_delta':0});p['scenarioDraft']['resources']['life']['bounds_rule']='rule/peer/reject_life';p['rules'].append({'id':'rule/peer/reject_life','kind':'calculation_rule','contract':'resource.bounds','implementation':{'type':'expression','expression':"{'accepted':False,'value':inputs.candidate}"}})
 s=make(p);before=s.checkpoint()
 with pytest.raises(ValueError):s.ctx.lifecycle.exit('actor')
 assert s.checkpoint()==before and s.ctx.get('actor',('runtime','exit_accounting_claim')) is None;capture(s,'last_bounds_failure')
def test_resource_change_reaction_cannot_create_second_combat_death_or_exit_credit():
 p=fixture({'base_life_loss':1,'kills_delta':1,'leaks_delta':0},True);watch={'id':'unit/peer/watcher','kind':'entity','components':{'attributes':{'base':{'max_hp':1000}},'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{},'buffs':{'initial':['buff/peer/resource_watch']},'lifecycle':{'policy':'policy/ark_lifecycle'}}};p['entities'].append(watch);p['scenarioDraft']['initialEntities'].append({'definition':watch['id'],'instanceAlias':'watcher','position':{'row':0,'col':2}})
 p['buffs']=[{'id':'buff/peer/resource_watch','kind':'buff','events':[{'event':'resource.changed','condition':"event.payload.target == 1 and event.payload.resource == 'life'",'effects':[{'op':'retire','target':2,'parameters':{'reason':'dead'}}]}]}]
 s=make(p);s.advance(25);capture(s,'resource_event_retire');assert (s.ctx.state()['kills'],s.ctx.state()['leaks'])==(1,0) and not [e for e in s.session.events if e['type']=='entity.died'] and s.ctx.resources.current('actor','hp')==95000
