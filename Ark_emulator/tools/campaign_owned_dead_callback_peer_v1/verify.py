"""Fresh independent actual owned-interrupt callback proof."""
import argparse,copy,hashlib,json,os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SHA='054b5a21d874801046531bd4786a0d5c8e4dbdb87c7769855debb5237b269dda'
CORE='737e23225fd3c3b9f3d75d9f005a6a5f2ce4a28b0f29fd444276c805cca49e87'
def main():
 a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);args=a.parse_args()
 sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 freeze=ROOT/'validation/campaign/campaign_owned_interrupt_callbacks_v1/freeze.functional.v1.json';assert sha(freeze)==SHA
 f=json.loads(freeze.read_bytes());runtime=Path(f['candidate']);sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
 from ark_sim import Compiler,Engine
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.contracts import thaw
 from ark_sim.tools.replay import replay
 from ark_sim.domains import owned_interrupt_callbacks as oc
 from tools.campaign_owned_dead_callback_peer_v1.fixtures import package,RESOURCE,CAST,BUFF
 assert implementation_digest()==CORE
 paths=[freeze,Path(__file__),ROOT/'tools/campaign_owned_dead_callback_peer_v1/fixtures.py']+[runtime/p for p in f['inventory']];before={str(p):sha(p) for p in paths};assert all(sha(runtime/p)==v for p,v in f['inventory'].items())
 log=Path(os.environ['ARKSIM_RUN_DIR']);facts={};results=[]
 def cp(s):return json.loads(json.dumps(s.checkpoint()))
 def create(p):return Engine.create(Compiler().compile(p),seed=913)
 def stores(s):return {'world':s.session.world.snapshot(),'jobs':s.session.scheduler.snapshot(),'events':s.session._events.snapshot(),'RNG':s.session.random.snapshot(),'cache':s.ctx.attributes.checkpoint_cache()}
 def value(s,alias='targetB'):return s.ctx.resources.current(alias,RESOURCE)
 def ledger(s):return thaw(s.ctx.get('system/battle',('owned_interrupt_callbacks',),{}))
 def full(p,label,at=6,end=12):
  s=create(p);s.advance(at);path=log/(label+'.checkpoint.json');path.write_text(json.dumps(cp(s)),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()));assert cp(s)==cp(r);s.advance(end-at);r.advance(end-at);h=replay(s.program,s.export_replay());assert cp(s)==cp(r)==cp(h);facts[label]={'CP_head_equal':True,'checkpoint_sha':sha(path),'program':s.program.fingerprint,'ledger':ledger(s),'B':value(s)};return s
 def live_death():
  s=full(package(),'death');assert value(s)==51.75 and value(s,'targetA')==43 and s.ctx.resources.current('caster','hp')==0;assert len(ledger(s)['instances'])==1
  facts['death']['events']=[thaw(e) for e in s.session.events if e['type'] in ('command.accepted','command.rejected','ability.interrupted','buff.owned_interrupt.complete')]
 def finite_and_disabled():
  for mode in ['expired','removed','inactive','noopt','disallow']:
   p=package();b=next(x for x in p['definitions'] if x['id']==BUFF)
   if mode=='expired':b['duration_seconds']=.1
   if mode=='removed':p['scenarioDraft']['scheduledEffects']=[{'at':4,'effect':{'op':'remove_buff','target':2,'buff':BUFF}}]
   if mode=='inactive':
    b['active_rule']='rule/peer/disabled_callback';p['definitions'].append({'id':'rule/peer/disabled_callback','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'False'}})
   if mode=='noopt':b['events'][0].pop('owned_callback')
   if mode=='disallow':b['events'][0]['owned_callback']['allow_owner_inactive']=False
   s=full(p,mode);assert value(s)==59 and not ledger(s).get('instances')
 def withdraw_live():
  p=package();p['scenarioDraft']['commands'][-1]={'at':7,'action':'withdraw','source':'caster'};s=full(p,'withdraw');assert value(s)==51.75 and len(ledger(s)['instances'])==1
 def foreign_buff():
  p=package();hold=next(x for x in p['definitions'] if x['id']==CAST);hold['activation'].pop('on_start');killer=next(x for x in p['definitions'] if x['id']=='unit/peer/callback_killer');give='ability/peer/foreign_grant';killer['components']['abilities'].append(give)
  p['definitions'].append({'id':give,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/peer/callback_caster','timeline':[{'at':0,'effect':{'op':'apply_buff','target':'selected','buff':BUFF}}]});p['scenarioDraft']['commands'].insert(0,{'at':0,'action':'skill','source':'killer','ability':give})
  s=full(p,'foreign');assert value(s)==59 and not ledger(s).get('instances');facts['foreign']['actual_application']=[thaw(e) for e in s.session.events if e['type']=='buff.owned_interrupt.application'];assert len(facts['foreign']['actual_application'])==1
 def direct_authority():
  s=full(package(),'authority');row=next(iter(ledger(s)['instances'].values()));base=stores(s);errors=[]
  for token in [object(),s.ctx.abilities._owned_interrupt_token]:
   try:oc.dispatch(s.ctx.abilities,[copy.deepcopy(row)],row['event'],token)
   except (ValueError,RuntimeError) as e:errors.append(str(e))
   else:raise AssertionError('Direct historical dispatch accepted')
   assert stores(s)==base
  effect=copy.deepcopy(row['subscription']['effects'][0])
  try:s.ctx.effects.execute(row['source'],[s.session.world.resolve('targetB')],effect,cast={'owned_interrupt_callback':{'id':row['id'],'issued':row['issued_event'],'effect_index':0}})
  except (ValueError,RuntimeError) as e:errors.append(str(e))
  else:raise AssertionError('Copied metadata obtained inactive source permission')
  assert stores(s)==base;facts['authority_errors']=errors
 def forged_task():
  s=full(package(),'forged_task');row=next(iter(ledger(s)['instances'].values()));observed=[]
  def forged(session,payload):
   entry=stores(s)
   try:oc.dispatch(s.ctx.abilities,[copy.deepcopy(row)],row['event'],s.ctx.abilities._owned_interrupt_token)
   except (ValueError,RuntimeError) as e:observed.append({'error':str(e),'same':stores(s)==entry,'task':thaw(session.current_task)})
   else:raise AssertionError('Unowned real scheduler task obtained capability')
  s.session.register_handler('peer.forged.callback',forged);s.session.schedule('peer.forged.callback',{'event':row['event']},s.session.time+1);s.advance(2);assert len(observed)==1 and observed[0]['same'] and value(s)==51.75;facts['forged_task']=observed
 def restored_tamper():
  s=full(package(),'restore');good=cp(s)
  def state(c):return next(x for x in c['kernel']['world']['entities'] if x['definition_id']=='system/battle')['components']['owned_interrupt_callbacks']
  errors=[]
  for key in ['erase','event','application','clock','generation','source','coherent_generation']:
   c=copy.deepcopy(good);st=state(c);row=next(iter(st['instances'].values()))
   if key=='erase':st['instances'].clear();st['next_id']=1
   elif key=='event':row['event']=1
   elif key=='application':row['buff']['owned_interrupt_application_event']=1
   elif key=='clock':row['captured_at']+=1
   elif key=='generation':row['buff']['generation']+=1
   elif key=='source':row['source']=s.session.world.resolve('killer')
   else:
    row['buff']['generation']+=1
    record=next(e for e in c['kernel']['events']['records'] if e['id']==row['issued_event']);record['payload']['buff']['generation']+=1
   try:Engine.restore(s.program,c)
   except (ValueError,RuntimeError,KeyError) as e:errors.append({'mutation':key,'error':str(e)})
   else:raise AssertionError('Tamper accepted '+key)
  facts['tamper']=errors
 def late_fault():
  s=create(package());s.advance(6);captures=[];draws=[];old=s.ctx.effects.execute
  def capture():
   if s.session._atomic_depth==0 and s.session.current_task:captures.append({'stores':stores(s),'clock':s.session.time,'task':thaw(s.session.current_task)})
   return None
  s.session.register_atomic_participant('peer.callback.boundary',capture,lambda _:None)
  def broken(source,targets,effect,*args_,**kw):
   result=old(source,targets,effect,*args_,**kw)
   if effect.get('op')=='modify_resource' and s.ctx.abilities._owned_interrupt_effect_scopes:
    assert value(s)==51.75
    for _ in range(2):draws.append(s.session.random.sample('peer/dead/fault'))
    raise ValueError('peer actual debit then RNG2 fault')
   return result
  s.ctx.effects.execute=broken
  try:s.advance(2)
  except (ValueError,RuntimeError) as e:assert 'peer actual debit then RNG2 fault' in str(e)
  else:raise AssertionError('Late fault absent')
  assert len(draws)==2 and captures and stores(s)==captures[-1]['stores'];facts['late_fault']={'debit':51.75,'draws':2,'all5stores_equal':True,'boundary_clock':captures[-1]['clock'],'actual_clock':s.session.time,'failure':s.session._failure}
 for fn in [live_death,finite_and_disabled,withdraw_live,foreign_buff,direct_authority,forged_task,restored_tamper,late_fault]:
  try:fn();results.append({'case':fn.__name__,'passed':True})
  except Exception as e:results.append({'case':fn.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
 after={str(p):sha(p) for p in paths};code=0 if all(r['passed'] for r in results) and before==after else 1
 report={'schema':'ark-sim/dead-callback-independent-peer/v1','actual_exit':code,'core':implementation_digest(),'source_before':before,'source_after':after,'source_equal':before==after,'results':results,'facts':facts,'whole_or_source_consumer_approved':False};assert not args.output.exists();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
