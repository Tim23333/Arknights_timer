import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_owned_channel_phase_v1_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_resource_channel_v1.fixture import package as prior_package
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_owned_channel_phase_v1';FACT={};RESULT=[];ART=[]
def package(early=False):
 p=prior_package('phase_battery',3,99,17,.3,1.2);a=p['abilities'][0];a['channel_completion']={'mode':'after_last_owned_channel','post_delay_seconds':.23};a['duration_seconds']=.2;a['timeline'][0]['at_seconds']=.2;a['timeline'][0].pop('at');a['cooldown_seconds']=.4
 p['definitions'][0]['motion']['parameters']['speed']=100
 if early:
  p['selectors'].append({'id':'selector/phase/source','kind':'selector','region':{'type':'all'},'filters':[{'tag':'source'}],'limit':1})
  p['abilities'].append({'id':'ability/phase/control','kind':'ability','activation':{'mode':'manual'},'selector':'selector/phase/source','timeline':[{'at':0,'effect':{'op':'apply_buff','buff':'buff/resource_channel/stun','duration_seconds':1}}]})
  p['entities'][1]['components']['abilities']=['ability/phase/control'];p['scenarioDraft']['commands'].append({'at':20,'action':'skill','source':'target','ability':'ability/phase/control'})
 return p
def create(p):return Engine.create(Compiler().compile(p),seed=91173)
def cpp(p,label,end=80):
 a=create(p);a.advance(end);b=create(p)
 for t in [14,48,51]:
  b.advance(t-b.session.time);f=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(f,h));assert b.checkpoint()==before
 b.advance(end-b.session.time);head=replay(a.program,a.export_replay());assert a.checkpoint()==b.checkpoint()==head.checkpoint();assert list(a.session.events)==list(b.session.events)==list(head.session.events);return a
def finite():
 s=cpp(package(),'finite');x=next(iter(s.ctx.attachments.state()['instances'].values()));ev=[thaw(e) for e in s.session.events if e['type'].startswith(('attachment.','ability.'))];FACT['finite']={'attachment':x,'events':ev,'battery':s.ctx.resources.current('target','phase_battery')};issued=next(e for e in ev if e['type']=='ability.channel_post.issued');done=next(e for e in ev if e['type']=='ability.finished' and e['payload']['ability']=='ability/resource_channel/start');assert done['time']==issued['time']+7 and x['packets']==4 and s.ctx.resources.current('target','phase_battery')==29
 def atomicnoop():
  before=s.checkpoint();s.ctx.abilities.finish(s.session,{'source':s.session.world.resolve('source'),'cast':'invalid'});assert s.checkpoint()==before
 atomicnoop()
def early():
 s=cpp(package(True),'early');ev=[thaw(e) for e in s.session.events if e['type'].startswith(('attachment.','ability.'))];FACT['early']=ev;issued=next(e for e in ev if e['type']=='ability.channel_post.issued');done=next(e for e in ev if e['type']=='ability.finished' and e['payload']['ability']=='ability/resource_channel/start');assert issued['time']==21 and done['time']==28
 def exact():return True

def tamper():
 s=create(package());s.advance(49);c=s.checkpoint();actor=next(e for e in c['kernel']['world']['entities'] if e['id']==s.session.world.resolve('source'));cast=next(iter(actor['components']['runtime']['casts'].values()));FACT['post_checkpoint']=cast;rows=[]
 def modify(b,label):
  owner=next(e for e in b['kernel']['world']['entities'] if e['id']==s.session.world.resolve('source'));cc=next(iter(owner['components']['runtime']['casts'].values()));l=cc['channel_post']
  if label=='missing':cc.pop('channel_post')
  elif label=='due':l['task']['at']+=1;cc['finish_at']+=1
  elif label=='stamp':l['owner_stamp']['life']+=1
  elif label=='clockcause':l['clock_proofs'][0]['cause']=1
  elif label=='copiedtask':l['task']['id']+=1
  elif label=='completed':l['completed_events'][0]+=1
 for label in ['missing','due','stamp','clockcause','copiedtask','completed']:
  b=copy.deepcopy(c);modify(b,label)
  try:Engine.restore(s.program,b)
  except Exception as e:rows.append({'case':label,'rejected':True,'error':str(e)})
  else:rows.append({'case':label,'rejected':False})
 FACT['tamper']=rows;assert all(x['rejected'] for x in rows)
 before=s.checkpoint();s.ctx.abilities.finish(s.session,{'source':s.session.world.resolve('source'),'cast':cast['id']});assert s.checkpoint()==before
 s2=create(package());s2.advance(14);before=s2.checkpoint()
 try:s2.ctx.abilities.channel_finished(s2.session.world.resolve('source'),next(iter(s2.ctx.get('source',('runtime','casts'),{}))))
 except ValueError as e:FACT['direct_callback']=str(e)
 else:raise AssertionError('Direct callback was accepted')
 assert s2.checkpoint()==before

def schema():
 rows=[]
 for value in [True,-1,float('nan')]:
  p=package();p['abilities'][0]['channel_completion']['post_delay_seconds']=value
  try:create(p)
  except Exception as e:rows.append({'value':str(value),'rejected':True,'error':str(e)})
  else:rows.append({'value':str(value),'rejected':False})
 FACT['schema']=rows;assert all(r['rejected'] for r in rows)
def guard():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json') and 'validation' not in p.parts}
BEFORE=guard()
for name,fn in [('actual_early_control_flag_relative_post_CPPhead',early)]:
 try:fn();RESULT.append({'case':name,'passed':True})
 except Exception:RESULT.append({'case':name,'passed':False,'traceback':traceback.format_exc()})
 after=guard();r={'core':implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULT) and after==BEFORE else 1,'results':RESULT,'facts':FACT,'CP':ART,'source_before':BEFORE,'source_after':after,'source_guard_equal':after==BEFORE,'comparison_exclusions':[]};(OUT/'author.early_final.v4.json').write_text(json.dumps(r,indent=2),encoding='utf8')
print(json.dumps({'exit':r['actual_exit'],'results':RESULT}));raise SystemExit(r['actual_exit'])
