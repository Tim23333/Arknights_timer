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
 if early:p['scenarioDraft']['scheduledEffects']=[{'at':20,'source':'target','target':'source','effect':{'op':'apply_buff','buff':'buff/resource_channel/stun','duration_seconds':1}}]
 return p
def create(p):return Engine.create(Compiler().compile(p),seed=91173)
def cpp(p,label,end=80):
 a=create(p);a.advance(end);b=create(p)
 for t in [14,48,51]:
  b.advance(t-b.session.time);f=LOG/(label+str(t)+'.checkpoint.json');h=write_ordered(f,b.checkpoint());ART.append({'path':str(f),'sha256':h,'bytes':f.stat().st_size});before=b.checkpoint();b=Engine.restore(b.program,load_bound(f,h));assert b.checkpoint()==before
 b.advance(end-b.session.time);head=replay(a.program,a.export_replay());assert a.checkpoint()==b.checkpoint()==head.checkpoint();assert list(a.session.events)==list(b.session.events)==list(head.session.events);return a
def finite():
 s=cpp(package(),'finite');x=next(iter(s.ctx.attachments.state()['instances'].values()));ev=[thaw(e) for e in s.session.events if e['type'].startswith(('attachment.','ability.'))];FACT['finite']={'attachment':x,'events':ev,'battery':s.ctx.resources.current('target','phase_battery')};issued=next(e for e in ev if e['type']=='ability.channel_post.issued');done=next(e for e in ev if e['type']=='ability.finished');assert done['time']==issued['time']+7 and x['packets']==4 and s.ctx.resources.current('target','phase_battery')==29
 def atomicnoop():
  before=s.checkpoint();s.ctx.abilities.finish(s.session,{'source':1,'cast':'cast/1/1'});assert s.checkpoint()==before
 atomicnoop()
def early():
 s=cpp(package(True),'early');ev=[thaw(e) for e in s.session.events if e['type'].startswith(('attachment.','ability.'))];FACT['early']=ev;issued=next(e for e in ev if e['type']=='ability.channel_post.issued');done=next(e for e in ev if e['type']=='ability.finished');assert issued['time']==20 and done['time']==27
 def exact():return True

def tamper():
 s=create(package());s.advance(49);c=s.checkpoint();actor=next(e for e in c['kernel']['world']['entities'] if e['id']==1);cast=next(iter(actor['components']['runtime']['casts'].values()));FACT['post_checkpoint']=cast;rows=[]
 def modify(b,label):
  owner=next(e for e in b['kernel']['world']['entities'] if e['id']==1);cc=next(iter(owner['components']['runtime']['casts'].values()));l=cc['channel_post']
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
 before=s.checkpoint();s.ctx.abilities.finish(s.session,{'source':1,'cast':cast['id']});assert s.checkpoint()==before
 s2=create(package());s2.advance(14);before=s2.checkpoint()
 try:s2.ctx.abilities.channel_finished(1,'cast/1/1')
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

s=create(package());s.advance(20);r={'events':[thaw(e) for e in s.session.events if e['type'].startswith(('command.','ability.','attachment.'))],'casts':thaw(s.ctx.get(1,('runtime','casts'),{}))};(OUT/'startup.probe.v1.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
