import sys,os,json,hashlib,traceback
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_resource_channel_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.tools.replay import replay
from ark_sim.contracts import thaw
from tools.campaign_resource_channel_v1.fixture import package
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_resource_channel_v1';FACT={};RESULT=[];ART=[];REG=BUILTIN_PROVIDERS

def create(p):return Engine.create(Compiler().compile(p),providers=REG,seed=23177491)
def cpp(p,end=100,label='base'):
 a=create(p);a.advance(end);b=create(p)
 for tick in [6,15,40]:
  b.advance(tick-b.session.time);path=LOG/(label+str(tick)+'.checkpoint.json');h=write_ordered(path,b.checkpoint());ART.append({'path':str(path),'sha256':h,'bytes':path.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(path,h),providers=REG);assert b.checkpoint()==before
 b.advance(end-b.session.time);h=replay(a.program,a.export_replay(),providers=REG);assert a.checkpoint()==b.checkpoint()==h.checkpoint();assert list(a.session.events)==list(b.session.events)==list(h.session.events);return a

def clocks():
 a=cpp(package());x=next(iter(a.ctx.attachments.state()['instances'].values()));FACT['positive']={'channel':thaw(x),'charge':a.ctx.resources.current('target','battery_charge')};assert x['packets']==6 and x['held_until']==85 and a.ctx.resources.current('target','battery_charge')==11
 a=cpp(package('other_counter',-1.75,19,13,.4,1.65),label='negative');x=next(iter(a.ctx.attachments.state()['instances'].values()));FACT['negative']={'channel':thaw(x),'value':a.ctx.resources.current('target','other_counter')};assert x['packets']==5 and a.ctx.resources.current('target','other_counter')==4.25

def cancellation():
 facts=[]
 for reason,effect in [('source_invalid',{'op':'retire','target':2,'parameters':{'reason':'withdraw'}}),('target_invalid',{'op':'retire','target':3,'parameters':{'reason':'withdraw'}}),('source_flags',{'op':'apply_buff','target':2,'buff':'buff/resource_channel/stun'})]:
  p=package();p['scenarioDraft']['scheduledEffects']=[{'at':24,'effect':effect}];s=cpp(p,label=reason);x=next(iter(s.ctx.attachments.state()['instances'].values()));facts.append({'expected':reason,'actual':x['reason'],'packets':x['packets'],'value':s.ctx.resources.current('target','battery_charge')});assert not x['active'] and x['reason']==reason and x['packets']==2
 FACT['cancellation']=facts

def permissions():
 s=create(package());s.advance(15);x=next(iter(s.ctx.attachments.state()['instances'].values()));before=s.checkpoint()
 try:s.ctx.attachments.step(s.session,{'attachment':x['id'],'generation':x['generation']})
 except ValueError as e:FACT['direct_step']=str(e)
 else:raise AssertionError('Direct step authorized resource packet')
 assert before==s.checkpoint()
 try:s.ctx.effects.execute('source',[s.session.world.resolve('target')],{'op':'modify_resource','resource':'battery_charge','delta':99},cast={'resource_channel':{'attachment':x['id'],'generation':x['generation'],'source':2,'target':3,'cast':x['cast'],'task':x['task']}})
 except ValueError as e:FACT['fake_cast']=str(e)
 else:raise AssertionError('Fake cast metadata authorized packet')
 assert before==s.checkpoint()
 cp=s.checkpoint();facts=[]
 for field in ['packets','due','task_seq','generation']:
  bad=deepcopy(cp);instance=next(e for e in bad['kernel']['world']['entities'] if e['id']==1)['components']['attachments']['instances'][x['id']];instance[field]+=1
  try:Engine.restore(s.program,bad,providers=REG)
  except Exception as e:facts.append({'field':field,'rejected':True,'message':str(e)})
  else:facts.append({'field':field,'rejected':False})
 FACT['tamper']=facts;assert all(f['rejected'] for f in facts)

def invalid_profiles():
 for label,change in [('integral',lambda d:d.update(damage_integral=True)),('clockabsent',lambda d:d.pop('hit_interval_seconds')),('emptyresource',lambda d:d['effect'].update(resource=''))]:
  p=package();change(p['definitions'][0])
  try:create(p)
  except Exception as e:FACT[label]={'rejected':True,'error':str(e)}
  else:raise AssertionError('Invalid resource channel accepted '+label)

def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.parts}
BEFORE=guard()
for name,fn in [('finite_positive_negative_capacity_and_CPPhead',clocks),('actual_source_target_and_control_cancellation_CPP',cancellation),('owned_tasks_cast_and_restore_permission',permissions),('no_integral_and_explicit_resource_clock',invalid_profiles)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULT) and BEFORE==after else 1,'results':RESULT,'facts':FACT,'artifacts':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':BEFORE==after,'comparison_exclusions':[]};(OUT/'author.initial.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'actual_exit':r['actual_exit'],'results':RESULT}));raise SystemExit(r['actual_exit'])
