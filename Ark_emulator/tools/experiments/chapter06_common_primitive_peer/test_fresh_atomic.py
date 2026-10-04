from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from tools.experiments.chapter06_common_primitive_peer.test_no_source_floor import package,request,make,registry,capture,events,INPUTS,CAPTURES

def test_actor_sourced_periodic_late_rule_failure_also_rolls_back_first_resource_effect():
 p=package();p['rules'].append({'id':'rule/peer/actor_explode','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':'1/0'}],'output':'nodes.result'}});p['entities'][0]['components']['resources']['meter']={'initial':0,'capacity':10};p['buffs'][0]['effects']=[{'op':'modify_resource','resource':'meter','delta':1},{'op':'damage','damage_type':'true','scale':1,'rules':{'damage.pipeline':'rule/peer/actor_explode'}}];s=make(p);s.advance(3)
 with pytest.raises(Exception):s.advance(1)
 capture(s,'actor_late_failure');assert s.ctx.resources.current('owner','meter')==0 and s.ctx.resources.current('owner','hp')==71 and not events(s,'damage.accepted')

def late_bounds(inputs,params,context):
 if inputs['candidate']<20:raise ValueError('independent late health bound')
 return {'accepted':True,'value':min(inputs['candidate'],inputs['capacity']),'overflow':0}

def test_true_nosource_late_actual_health_bounds_failure_rolls_back_both_packets():
 p=package();p['rules'].append({'id':'rule/peer/late_bound','kind':'rule','contract':'resource.bounds','implementation':{'type':'provider','provider':'peer/late_bound'}});p['entities'][0]['components']['resources']['hp']['bounds_rule']='rule/peer/late_bound';p['buffs'][0]['effects']=[request(True),request(True)];r={**registry(),'peer/late_bound':{'callable':late_bounds,'version':'independent1'}};INPUTS.append(deepcopy(p));s=Engine.create(Compiler(providers=r).compile(p),providers=r);s.advance(3)
 with pytest.raises(Exception):s.advance(1)
 capture(s,'true_actual_bounds_late_failure');assert s.ctx.resources.current('owner','hp')==71 and not events(s,'damage.accepted') and not events(s,'damage.modification_bypassed')

def test_actual_timer_owner_public_retirement_prevents_stale_none_damage_after_retirement():
 p=package(False);p['abilities'].append({'id':'ability/peer/retire','kind':'ability','activation':{'mode':'manual','on_start':[{'op':'retire','target':2,'parameters':{'reason':'withdrawn'}}]},'timeline':[]});p['entities'][1]['components']['abilities'].append('ability/peer/retire');s=make(p);s.submit({'action':'skill','source':'controller','ability':'ability/peer/retire'},at=5);s.advance(15);capture(s,'retired_timer_owner');assert [e['time'] for e in events(s,'damage.accepted')]==[3] and not s.ctx.active('owner') and not s.ctx.get('owner',('buffs','instances'),[])
