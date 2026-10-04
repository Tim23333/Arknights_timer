import json
from tools.chapter08_ranged_runtime_context.clock_v2.test_source import ROOT,package,make,save_cp,OUT,MARKER
from tools.chapter08_ranged.policies_v1 import providers
from ark_sim import Compiler,Engine

def test_marker_exact_expiry_before_expire_job_uses_real_clock_no_mutation():
 p=package();next(b for b in p['buffs'] if b['id']==MARKER)['duration_seconds']=.5;program,s,reg=make(p);s.advance(14);before=s.checkpoint();assert s.ctx.spatial.eligible('source','selector/ch8/uoffcr/attack')==[s.session.world.resolve('target')];assert s.checkpoint()==before;s.advance(1);assert s.session.time==15;before=s.checkpoint();assert s.ctx.spatial.eligible('source','selector/ch8/uoffcr/attack')==[];assert s.checkpoint()==before;save_cp(p,s,program,reg,1,61,'expiry15plus1');assert not [e for e in s.session.events if e['type']=='ability.started' and e['time']>=60]

def test_source_target_retirement_public_skill_and_source_cancel_prelaunch():
 for target in ['source','target']:
  p=package();sid='selector/test/retire';p['selectors'].append({'id':sid,'kind':'selector','region':{'type':'all'},'filters':[{'field':{'path':['id'],'equals':2 if target=='source' else 3}}]});aid='ability/test/retire';p['abilities'].append({'id':aid,'kind':'ability','selector':sid,'activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]});p['entities'][-1]['components']['abilities']=[aid];program,s,reg=make(p);s.submit({'action':'skill','source':'target','ability':aid},at=5);save_cp(p,s,program,reg,4,30,'retire_'+target);assert not [e for e in s.session.events if e['type']=='damage.accepted'];before=s.checkpoint();assert s.ctx.spatial.eligible('source','selector/ch8/uoffcr/attack')==[];assert before==s.checkpoint()

def test_time_quantum_seconds_are_readonly_in_qualification_inputs_unchanged():
 p=package();p['rules'].append({'id':'rule/test/clock','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'test.readonly_clock'}});p['selectors'][1]['eligibility']['rule']='rule/test/clock';p['selectors'][1]['filters'].append({'field':{'path':['id'],'equals':3}});seen=[]
 def provider(inputs,params,context):
  assert type(context['time']) is int and context['seconds']==context['time']*context['quantum'] and context['quantum']==1/30;assert set(inputs)=={'source','candidate','selector','parameters','selection_states'}
  try:context['time']=999
  except TypeError:pass
  else:raise AssertionError('context mutable')
  try:inputs['candidate']['components']['resources']['hp']['current']=0
  except TypeError:pass
  else:raise AssertionError('input mutable')
  seen.append(context['time']);return {'accepted':True,'reason':'checked'}
 reg={**providers(),'test.readonly_clock':{'callable':provider,'version':'1'}};s=Engine.create(Compiler(providers=reg).compile(p),providers=reg);before=s.checkpoint();assert s.ctx.spatial.eligible('source','selector/ch8/uoffcr/attack')==[3];assert s.checkpoint()==before and seen==[0]
