"""Independent actual resource channel peer, only after exact final freeze."""
import argparse,sys,os,json,copy,hashlib,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',type=Path,required=True);parser.add_argument('--freeze-sha',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert sha(args.freeze)==args.freeze_sha=='dffd04f781fe2f79ffae043c2c572e77520c26bf8c101fdd4057ef83b7bdc567'
    freeze=json.loads(args.freeze.read_bytes());runtime=Path(freeze['candidate']);sys.path.insert(0,str(runtime));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    from tools.campaign_resource_channel_peer_v1.fixtures import package,terminal_package,providers,RESOURCE,PROFILE,ABILITY
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim' and implementation_digest()=='08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
    log=Path(os.environ['ARKSIM_RUN_DIR']);facts={};results=[]
    def cp(s):return json.loads(json.dumps(s.checkpoint()))
    def create(p):return Engine.create(Compiler(providers=providers()).compile(p),providers=providers(),seed=431)
    def state(s):return next(iter(s.ctx.attachments.state()['instances'].values()))
    def stores(s):return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'events':s.session._events.snapshot(),'random':s.session.random.snapshot(),'attribute_cache':s.ctx.attributes.checkpoint_cache()}
    def full(p,at,end,label):
        s=create(p);s.advance(at);path=log/(label+'.checkpoint.json');path.write_text(json.dumps(cp(s)),encoding='utf8');r=Engine.restore(s.program,json.loads(path.read_bytes()),providers=providers());assert cp(s)==cp(r);s.advance(end-at);r.advance(end-at);h=replay(s.program,s.export_replay(),providers=providers());assert cp(s)==cp(r)==cp(h)
        facts[label+'_proof']={'full_CP_head_equal':True,'program':s.program.fingerprint,'checkpoint_sha256':sha(path),'bytes':path.stat().st_size};return s
    def finite_math():
        s=full(package(),13,110,'finite');x=state(s);facts['finite']={'state':thaw(x),'remaining':s.ctx.resources.current('recipient',RESOURCE)};assert x['packets']==9 and x['reason']=='complete' and not x['active'] and facts['finite']['remaining']==23 and not s.ctx.get('recipient',('buffs','instances'))
        s=full(package(delta=1.25,initial=2,capacity=100,duration=1.1,interval=.3,maximum=3),9,45,'alternate');x=state(s);assert x['packets']==3 and x['reason']=='max_packets' and s.ctx.resources.current('recipient',RESOURCE)==5.75
    def freeze_and_negative():
        s=full(package(freeze=True),13,40,'freeze_positive');assert s.ctx.resources.current('recipient',RESOURCE)==11
        s=full(package(delta=-11,freeze=True),13,40,'freeze_negative');assert s.ctx.resources.current('recipient',RESOURCE)==0
        facts['freeze']={'positive_frozen':11,'negative_real_floor':0,'packet_clock_independent':True}
    def public_cancel_and_death():
        for source in ['sender','recipient']:
            p=package(capacity=101);p['scenarioDraft']['commands'].append({'at':17,'action':'withdraw','source':source});s=full(p,16,40,'withdraw_'+source);x=state(s)
            facts['withdraw_'+source]={'state':thaw(x),'value':s.ctx.resources.current('recipient',RESOURCE),'public_outcomes':[thaw(e) for e in s.session.events if e['type'] in ('command.accepted','command.rejected')]}
            assert not x['active'] and x['packets']==2 and s.ctx.resources.current('recipient',RESOURCE)==25
        p=package(capacity=101);p['scenarioDraft']['scheduledEffects']=[{'at':17,'effect':{'op':'apply_buff','target':2,'buff':'buff/peer/silence'}}];s=full(p,16,40,'silence');assert s.session.world.resolve('sender')==2 and state(s)['reason']=='source_flags' and state(s)['packets']==2
        for target in ['sender','recipient']:
            p=package(capacity=101);ref=2 if target=='sender' else 3;p['scenarioDraft']['scheduledEffects']=[{'at':17,'effect':{'op':'retire','target':ref,'parameters':{'reason':'dead'}}}];s=full(p,16,40,'dead_'+target);assert s.session.world.resolve(target)==ref and not state(s)['active'] and state(s)['packets']==2
    def terminal():
        s=full(terminal_package(),19,40,'terminal');facts['terminal']={'state':thaw(s.ctx.state()),'attachment':thaw(state(s)),'outcomes':[thaw(e) for e in s.session.events if e['type'] in ('command.accepted','command.rejected')]};assert s.ctx.state()['finished'] and not state(s)['active'] and state(s)['packets']==2
    def hidden_routes():
        for alias in ['sender','recipient']:
            p=package(capacity=101);actor=next(a for a in p['scenarioDraft']['initialEntities'] if a['instanceAlias']==alias);pos=actor['position']
            actor['route']={'motionMode':'WALK','startPosition':copy.deepcopy(pos),'endPosition':{'row':2,'col':4},'checkpoints':[{'type':'WAIT_FOR_SECONDS','time':.5,'position':copy.deepcopy(pos)},{'type':'DISAPPEAR','time':0,'position':copy.deepcopy(pos)},{'type':'WAIT_FOR_SECONDS','time':1,'position':copy.deepcopy(pos)},{'type':'APPEAR_AT_POS','time':0,'position':copy.deepcopy(pos)}],'transition_policy':{'rule':'rule/m9_living_transition','parameters':{'hidden_effects':'reject','hidden_auras':'suspend','launched_source_effects':'retain','resource_timers':'continue'}}}
            next(d for d in p['definitions'] if d['id']==ABILITY)['parameters']={'blocks_movement':False}
            s=full(p,13,40,'hidden_'+alias);facts['hidden_'+alias]={'state':thaw(state(s)),'hidden':s.ctx.route_hidden(alias),'events':[thaw(e) for e in s.session.events if e['type'] in ('movement.visibility_changed','ability.interrupted')]};expected_reason='cast_interrupted' if alias=='sender' else 'target_hidden';assert s.ctx.route_hidden(alias) and not state(s)['active'] and state(s)['packets']==2 and state(s)['reason']==expected_reason
    def authority():
        s=create(package());s.advance(3);x=thaw(state(s));before=stores(s)
        try:s.ctx.attachments.step(s.session,{'attachment':x['id'],'generation':x['generation']})
        except (ValueError,RuntimeError):pass
        assert stores(s)==before
        cast=thaw(s.ctx.abilities._active(x['source'],x['cast']));ability=s.program.definitions[x['ability']]
        try:s.ctx.attachments.begin(x['source'],x['target'],PROFILE,ability,cast)
        except (ValueError,RuntimeError):pass
        else:raise AssertionError('Copied active cast directly launched a resource channel')
        assert stores(s)==before
        try:s.ctx.effects.execute(x['source'],[x['target']],{'op':'modify_resource','resource':RESOURCE,'delta':999},cast={'resource_channel':{'attachment':x['id'],'generation':x['generation']}})
        except (ValueError,RuntimeError):pass
        else:raise AssertionError('Forged resource_channel tag permitted packet')
        assert stores(s)==before
        # A real newly scheduled but unowned task does not obtain packet scope.
        s.advance(14-s.session.time);x=thaw(state(s));fake=s.session.schedule('domain.attachment.step',{'attachment':x['id'],'generation':x['generation']},x['due'],phase=0)
        observed=[];original_handler=s.session._handlers['domain.attachment.step']
        def inspect_unowned_task(session,payload):
            if session.current_task['id']!=fake:return original_handler(session,payload)
            entry=stores(s)
            try:return original_handler(session,payload)
            finally:observed.append({'before':entry,'after':stores(s),'task':thaw(session.current_task)})
        s.session._handlers['domain.attachment.step']=inspect_unowned_task
        try:s.advance(x['due']-s.session.time+1)
        except (ValueError,RuntimeError):pass
        assert len(observed)==1 and observed[0]['before']==observed[0]['after'] and state(s)['packets']<=2 and s.ctx.resources.current('recipient',RESOURCE)<=23
        facts['authority']={'idle_direct_step_no_writes':True,'idle_direct_begin_rejected':True,'fake_resource_tag_rejected':True,'forged_real_task_due_at_packet14_no_any5store_write':True,'actual_forged_task':observed[0]['task']}
    def restored_tamper():
        s=create(package());s.advance(3);good=cp(s)
        def row(checkpoint):return next(e for e in checkpoint['kernel']['world']['entities'] if e['definition_id']=='system/battle')['components']['attachments']
        mutations=[('remove_all_instances',lambda c:row(c)['instances'].clear()),('change_target',lambda c:next(iter(row(c)['instances'].values())).__setitem__('target',2)),('wrong_due',lambda c:next(iter(row(c)['instances'].values())).__setitem__('due',999)),('wrong_generation',lambda c:next(iter(row(c)['instances'].values())).__setitem__('generation',999)),('borrow_issue',lambda c:next(iter(row(c)['instances'].values())).__setitem__('resource_issued_event',1))]
        rejected=[]
        for name,fn in mutations:
            bad=copy.deepcopy(good);fn(bad)
            try:Engine.restore(s.program,bad,providers=providers())
            except (ValueError,RuntimeError) as e:rejected.append({'case':name,'error':str(e)})
            else:raise AssertionError('Restored tamper accepted: '+name)
        s.advance(107);ended=cp(s);row(ended)['instances'].clear()
        try:Engine.restore(s.program,ended,providers=providers())
        except (ValueError,RuntimeError) as e:rejected.append({'case':'ended_missing_ledger','error':str(e)})
        else:raise AssertionError('Ended issue epoch erased without rejection')
        facts['tamper']=rejected
    def late_fault():
        s=create(package(capacity=101));s.advance(2);captures=[];draws=[];original=s.ctx.effects.execute
        def capture():
            task=s.session.current_task
            if s.session._atomic_depth==0 and task and task['kind']=='domain.attachment.step':captures.append({'stores':stores(s),'clock':s.session.time,'task':thaw(task)})
            return None
        s.session.register_atomic_participant('peer.resource.actual_task_boundary',capture,lambda _:None)
        def broken(source,targets,effect,*args_,**kwargs):
            result=original(source,targets,effect,*args_,**kwargs)
            if effect.get('op')=='modify_resource' and s.session.current_task and s.session.current_task['kind']=='domain.attachment.step':
                assert s.ctx.resources.current('recipient',RESOURCE)==18
                for _ in range(2):draws.append(s.session.random.sample('peer/resource/fault'))
                raise ValueError('Independent late fault after actual resource settlement and two RNG draws')
            return result
        s.ctx.effects.execute=broken
        try:s.advance(1)
        except (ValueError,RuntimeError) as e:assert 'after actual resource settlement and two RNG draws' in str(e)
        else:raise AssertionError('Actual packet fault missing')
        assert len(draws)==2 and len(captures)==1 and stores(s)==captures[0]['stores'] and s.session.time==captures[0]['clock']==2
        facts['fault']={'actual_resource_changed_before_fault':18,'actual_RNG_draws':2,'all5_stores_equal':True,'actual_task':captures[0]['task'],'failure_record':s.session._failure,'framework_clock_at_owned_atomic_boundary':2}
    def missing_resource():
        p=package();next(e for e in p['definitions'] if e['id']=='unit/peer/channel_target')['components']['resources'].pop(RESOURCE);s=create(p)
        try:s.advance(3)
        except (ValueError,RuntimeError,KeyError) as e:facts['missing_resource_error']=str(e);assert RESOURCE in str(e)
        else:raise AssertionError('Missing resource silently accepted')
    paths=[args.freeze,Path(__file__),ROOT/'tools/campaign_resource_channel_peer_v1/fixtures.py']+[p for p in (runtime/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']];before={str(p):sha(p) for p in paths};core=implementation_digest()
    for fn in [finite_math,freeze_and_negative,public_cancel_and_death,terminal,hidden_routes,authority,restored_tamper,late_fault,missing_resource]:
        try:fn();results.append({'case':fn.__name__,'passed':True})
        except Exception as e:results.append({'case':fn.__name__,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
    after={str(p):sha(p) for p in paths};code=0 if all(r['passed'] for r in results) and before==after else 1
    report={'schema':'ark-sim/independent-resource-channel-peer/v1','core_before':core,'core_after':implementation_digest(),'freeze_sha256':args.freeze_sha,'actual_exit':code,'source_before':before,'source_after':after,'source_equal':before==after,'results':results,'facts':facts,'whole_or_client_verified':False};assert not args.output.exists();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'actual_exit':code,'results':results}));return code
if __name__=='__main__':raise SystemExit(main())
