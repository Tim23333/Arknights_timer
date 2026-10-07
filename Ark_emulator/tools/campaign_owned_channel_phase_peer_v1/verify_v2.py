"""Independent new phaseV2 peer: alternate clock, multichannel and authority."""
import sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_owned_channel_phase_v2_candidate').resolve();sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_resource_channel_peer_v1.fixtures import package,providers,PROFILE,ABILITY
LOG=Path(os.environ['ARKSIM_RUN_DIR']);OUT=ROOT/'validation/campaign/campaign_owned_channel_phase_peer_v1';OUT.mkdir(parents=True,exist_ok=True);FACT={};sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fixture(multi=False,post=True):
    p=package(duration=.41,interval=.13,capacity=83);p['definitions'].append({'id':'ruleset/peer/phase17','kind':'ruleset','extends':'ruleset/ark_standard','quantum':1/17});p['scenarioDraft']['ruleset']='ruleset/peer/phase17'
    a=next(d for d in p['definitions'] if d['id']==ABILITY);a['duration_seconds']=2;a['timeline'][0].pop('at');a['timeline'][0]['at_seconds']=.4
    if post:a['channel_completion']={'mode':'after_last_owned_channel','post_delay_seconds':.23}
    if multi:
        b=copy.deepcopy(next(d for d in p['definitions'] if d['id']==PROFILE));b['id']='attachment/peer/resource_second';b['duration_seconds']=.83;p['definitions'].append(b);a['timeline'].append({'at_seconds':.7,'effect':{'op':'begin_attachment','attachment':b['id']}})
    return p
def create(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=817)
def cp(s):return json.loads(json.dumps(s.checkpoint()))
def stores(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'events':s.session._events.snapshot(),'random':s.session.random.snapshot(),'cache':s.ctx.attributes.checkpoint_cache()}
def cast(s):return next(iter(s.ctx.get('sender',('runtime','casts')).values()))
def proof(p,label,pins,end):
    s=create(p);s.advance(end);r=create(p);rows=[]
    for at in pins:
        r.advance(at-r.session.time);path=LOG/(label+str(at)+'.checkpoint.json');path.write_text(json.dumps(cp(r)),encoding='utf8');r=Engine.restore(r.program,json.loads(path.read_bytes()),providers=providers());rows.append({'at':at,'SHA':sha(path),'bytes':path.stat().st_size})
    r.advance(end-r.session.time);h=replay(s.program,s.export_replay(),providers=providers());assert cp(s)==cp(r)==cp(h);FACT[label]={'CPP_head':True,'pins':rows,'program':s.program.fingerprint};return s
def clock_math():
    s=proof(fixture(),'single',[7,10,17,19],25);events=[thaw(e) for e in s.session.events if e['type'].startswith('ability.channel') or e['type']=='ability.finished'];FACT['single_events']=events
    started=next(e for e in events if e['type']=='ability.channel_post.started');assert started['time']==16 and started['payload']['due']==20;assert next(e for e in events if e['type']=='ability.finished')['time']==20
    s=proof(fixture(True),'multi',[10,17,30,32],40);events=[thaw(e) for e in s.session.events if e['type'].startswith('ability.channel') or e['type']=='ability.finished'];FACT['multi_events']=events;assert next(e for e in events if e['type']=='ability.channel_post.started')['time']==29 and next(e for e in events if e['type']=='ability.finished')['time']==33
    s=proof(fixture(True,False),'legacy',[10,30,34],40);events=[e for e in s.session.events if e['type']=='ability.finished'];assert events[0]['time']==35 and not [e for e in s.session.events if e['type'].startswith('ability.channel_post')]
def declared_rule():
    p=fixture(True);a=next(d for d in p['definitions'] if d['id']==ABILITY);rid='rule/peer/recovery';a['rules']={'ability.recovery':rid};p['definitions'].append({'id':rid,'kind':'rule','contract':'ability.recovery','implementation':{'type':'expression','expression':'inputs.recovery_parameters.seconds + context.source.components.attributes.base.atk / 1000'}})
    s=proof(p,'custom_rule',[30,33],40);event=next(e for e in s.session.events if e['type']=='ability.channel_post.started');FACT['custom_rule_due']=event['payload']['due'];assert event['payload']['due']==34
def authority():
    for at,label in [(2,'pre'),(10,'active'),(17,'post'),(21,'late')]:
        s=create(fixture());s.advance(at);before=stores(s);casts=s.ctx.get('sender',('runtime','casts'));cid=next(iter(casts)) if casts else 'cast/2/1';payload={'source':s.session.world.resolve('sender'),'cast':cid}
        for _ in range(2):s.ctx.abilities.finish(s.session,payload);assert stores(s)==before
        FACT['direct_'+label]=True
    s=create(fixture());s.advance(17);c=thaw(cast(s));lease=c['channel_post'];source=s.session.world.resolve('sender');before=stores(s)
    from ark_sim.domains.channel_phases import completed
    e=next(e for e in s.session.events if e['id']==lease['completed_events'][-1]);x=s.ctx.attachments.current(e['payload']['attachment'])
    try:completed(s.ctx.abilities,source,c,x['id'],e['id'])
    except (ValueError,RuntimeError):pass
    else:raise AssertionError('Ended event borrowed as live completion permission')
    assert stores(s)==before
    # Real unowned finish task is tested at the actual post deadline.
    s.advance(20-s.session.time);c=thaw(cast(s));lease=c['channel_post'];fake=s.session.schedule('domain.ability.finish',{'source':source,'cast':c['id']},20,phase=0);old=s.session._handlers['domain.ability.finish'];observed=[]
    def handler(session,payload):
        if session.current_task['id']!=fake:return old(session,payload)
        before=stores(s)
        try:return old(session,payload)
        finally:observed.append((before,stores(s)))
    s.session._handlers['domain.ability.finish']=handler;s.advance(1);assert len(observed)==1 and observed[0][0]==observed[0][1]
    FACT['fake_due_task_no5store_write']=True
    s=create(fixture());s.advance(17);c=thaw(cast(s));payload={'source':2,'cast':c['id']};before=stores(s);original_active=s.session._active_task
    s.session._active_task=copy.deepcopy(c['channel_post']['task'])
    try:s.ctx.abilities.finish(s.session,payload)
    finally:s.session._active_task=original_active
    assert stores(s)==before;FACT['borrowed_real_task_dict_without_dispatch_rejected']=True
def same_tick_scope():
    s=create(fixture());old=s.ctx.attachments.stop;rows=[]
    def stop(uid,reason):
        result=old(uid,reason);x=s.ctx.attachments.current(uid)
        if x and not x['active'] and not rows:
            c=thaw(s.ctx.abilities._active(x['source'],x['cast']));e=next(e for e in reversed(list(s.session.events)) if e['type']=='attachment.finished');before=stores(s)
            from ark_sim.domains.channel_phases import completed
            try:completed(s.ctx.abilities,x['source'],c,uid,e['id'])
            except (ValueError,RuntimeError):rows.append({'rejected':True,'time':s.session.time,'stores_equal':stores(s)==before})
            else:raise AssertionError('Same-tick real ended event reborrow accepted')
        return result
    s.ctx.attachments.stop=stop;s.advance(18);assert len(rows)==1 and rows[0]['stores_equal'];FACT['same_tick']=rows
def silent():
    p=fixture();p['scenarioDraft']['scheduledEffects']=[{'at':11,'effect':{'op':'apply_buff','target':2,'buff':'buff/peer/silence'}}];s=proof(p,'silent12',[10,12,14],20);events=[e for e in s.session.events if e['type']=='ability.channel_post.started'];assert events[0]['time']==11 and events[0]['payload']['due']==15;FACT['silent12_finish']=next(e['time'] for e in s.session.events if e['type']=='ability.finished');assert FACT['silent12_finish']==15
def tamper():
    s=create(fixture());s.advance(17);good=cp(s)
    def c(cp_):return next(e for e in cp_['kernel']['world']['entities'] if e['id']==2)['components']['runtime']['casts']['cast/2/1']
    mutations=[('lease_missing',lambda b:c(b).pop('channel_post')),('scope_source',lambda b:c(b)['channel_post'].__setitem__('source',3)),('due',lambda b:c(b)['channel_post']['task'].__setitem__('at',18)),('phase',lambda b:c(b)['channel_post']['task'].__setitem__('phase',0)),('seq',lambda b:c(b)['channel_post']['task'].__setitem__('seq',777)),('cause',lambda b:c(b)['channel_post']['clock_proofs'][0].__setitem__('cause',1)),('clock',lambda b:c(b)['channel_post']['clock_proofs'][0]['context'].__setitem__('time',1)),('operand',lambda b:c(b)['channel_post']['clock_proofs'][0]['inputs']['recovery_parameters'].__setitem__('seconds',.01))]
    rows=[]
    for name,fn in mutations:
        b=copy.deepcopy(good);fn(b)
        try:Engine.restore(s.program,b,providers=providers())
        except (ValueError,RuntimeError) as e:rows.append({'name':name,'error':str(e)})
        else:raise AssertionError('Restored phase tamper accepted '+name)
    FACT['tamper']=rows
    # Coherently edit World lease, issued event, actual scheduled task and
    # quantization ledger values. Only pure selected-rule recomputation can
    # distinguish this internally self-consistent false timing.
    b=copy.deepcopy(good);cs=c(b);lease=cs['channel_post'];lease['units']=2;lease['task']['at']=18;cs['finish_at']=18;proof=lease['clock_proofs'][1];proof['value']=2
    events=b['kernel']['events']['records']
    for e in events:
        if e['id']==proof['event']:e['payload']['value']=2;e['payload']['trace']['value']=2
        if e['id']==lease['issued']:e['payload']=copy.deepcopy({k:v for k,v in lease.items() if k!='issued'})
    for task in b['kernel']['scheduler']['tasks']:
        if task['id']==lease['task']['id']:task['at']=18
    try:Engine.restore(s.program,b,providers=providers())
    except (ValueError,RuntimeError) as e:
        FACT['coherent_quantization_tamper_error']=str(e);assert 'pure clock trace/binding/value differs' in str(e)
    else:raise AssertionError('Coherent timing forgery bypassed pure rule recomputation')
def fault():
    s=create(fixture(True));s.advance(29);captures=[];original=s.ctx.emit;draws=[]
    def capture():
        if s.session.time==29 and s.session._atomic_depth==0:captures.append(stores(s))
        return None
    s.session.register_atomic_participant('peer.phase.true_post_boundary',capture,lambda _:None)
    def emit(type_,payload,cause=None):
        result=original(type_,payload,cause)
        if type_=='ability.channel_post.started':
            assert cast(s)['channel_post']['task']['at']==33
            for _ in range(2):draws.append(s.session.random.sample('peer/phase/fault'))
            raise ValueError('Peer late post fault after real task, lease and event plus RNG2')
        return result
    s.ctx.emit=emit
    try:s.advance(1)
    except (ValueError,RuntimeError) as e:assert 'real task, lease and event plus RNG2' in str(e)
    else:raise AssertionError('True late post fault absent')
    assert len(draws)==2 and captures and stores(s)==captures[-1];FACT['fault']={'actual_RNG':2,'all5stores_equal_at_actual_last_atomic_boundary':True,'time':s.session.time,'failure':s.session._failure}
def main():
    freeze=ROOT/'validation/campaign/campaign_owned_channel_phase_v2/freeze.functional.v2.json';assert sha(freeze)=='01856e38162f8c274e9186f6bee39a06b9f94c32ef26197b1f278e21dd7405cb';core=implementation_digest();assert core=='da218736ae42600b5d80653b411508b13438e9002b18af3f04233285ac3cb226';files=[freeze,Path(__file__),ROOT/'tools/campaign_resource_channel_peer_v1/fixtures.py']+[p for p in (CAND/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];before={str(p):sha(p) for p in files};results=[]
    for f in [clock_math,declared_rule,authority,same_tick_scope,silent,tamper,fault]:
        try:f();results.append({'case':f.__name__,'passed':True})
        except Exception as e:results.append({'case':f.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in files};code=0 if all(r['passed'] for r in results) and before==after else 1;path=OUT/'phase.v2.actual.v2.json';assert not path.exists();path.write_text(json.dumps({'core_before':core,'core_after':implementation_digest(),'actual_exit':code,'source_before':before,'source_after':after,'source_equal':before==after,'results':results,'facts':FACT,'whole_or_dmech_approved':False},indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
