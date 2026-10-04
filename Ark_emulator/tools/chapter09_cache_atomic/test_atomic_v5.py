"""Focused savepoint/cache tests on frozen V5; original cases stay unchanged."""
import importlib.util,json,copy,sys,hashlib,traceback
from pathlib import Path
spec=importlib.util.spec_from_file_location('own_v5',Path(__file__).with_name('review_v5.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
from ark_sim.kernel import Session
from ark_sim.contracts import freeze
from ark_sim.contracts import Intent
RESULTS=[]
def cp(s):return json.loads(json.dumps(s.checkpoint(),allow_nan=False))
def run(name,fn):
    try:fn();RESULTS.append({'case':name,'passed':True})
    except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
def nested_inner_then_outer():
    s=p.sim(p.joint_data()[0]);a,b=p.refs(s);s.ctx.attributes.value(b,'magic_resistance');before=cp(s);epoch=s.session.cache_epoch
    try:
        with s.session.atomic():
            s.ctx.set(b,('attributes','base','magic_resistance'),81);s.ctx.attributes.value(b,'magic_resistance');inner=cp_unrestricted(s)
            try:
                with s.session.atomic():
                    s.ctx.set(b,('attributes','base','magic_resistance'),99);s.ctx.attributes.value(b,'magic_resistance');s.session.random.sample('inner');s.session.schedule('domain.effect',{'source':a,'targets':[b],'effect':{'op':'emit','event':'pending'}},9);raise ValueError('inner failure')
            except ValueError:pass
            assert cp_unrestricted(s)==inner
            oldcause=s.ctx.attributes.cache[next(k for k in s.ctx.attributes.cache if k[2]=='magic_resistance')][1]
            assert s.ctx.attributes.value(b,'magic_resistance')==81;assert s.session.events[-1]['cause']==oldcause
            raise ValueError('outer failure')
    except ValueError:pass
    assert cp(s)==before and s.session.cache_epoch>epoch
    r=p.Engine.restore(s.program,cp(s));s.ctx.attributes.value(b,'magic_resistance');r.ctx.attributes.value(b,'magic_resistance');assert cp(s)==cp(r)
def cp_unrestricted(s):
    # Inspect trusted savepoint state while atomic is open; public checkpoint
    # properly remains unavailable here. No new runtime state is allocated.
    return {'kernel':s.session._state_data(),'attribute_cache':s.ctx.attributes.checkpoint_cache()}
def historical_identity():
    s=p.sim();a,b=p.refs(s);snap=freeze(s.ctx.capture_view(b));s.ctx.attributes.value(b,'magic_resistance',snapshot=snap);before=cp(s);cause=s.session.events[-1]['id']
    try:
        with s.session.atomic():s.ctx.set(b,('runtime','lifecycle_generation'),2);s.ctx.attributes.value(b,'magic_resistance');raise ValueError('undo lifecycle')
    except ValueError:pass
    assert cp(s)==before;s.ctx.attributes.value(b,'magic_resistance',snapshot=snap);assert s.session.events[-1]['type']=='calculation.cached' and s.session.events[-1]['cause']==cause
    s.ctx.set(b,('runtime','lifecycle_generation'),3);s.ctx.attributes.value(b,'magic_resistance',snapshot=snap);assert s.session.events[-1]['type']=='calculation'
def scope_rule_override():
    d=p.data();d['rules'].append({'id':'peer/attribute_override','kind':'calculation_rule','extends':'rule/ark_attribute_layers'})
    d['entities'][0]['rules']={'attributes.effective':'peer/attribute_override'};s=p.sim(d);a,b=p.refs(s)
    effects=[{'rules':{'attributes.effective':'peer/attribute_override'},'metadata':{'scope':'one'}},{'rules':{'attributes.effective':'peer/attribute_override'},'metadata':{'scope':'two'}}]
    for e in effects:s.ctx.attributes.value(a,'atk',effect=e)
    before=cp(s)
    try:
        with s.session.atomic():s.ctx.set(a,('runtime','rule_bindings','attributes.effective'),'rule/ark_attribute_layers');s.ctx.attributes.value(a,'atk');raise ValueError('scope rollback')
    except ValueError:pass
    assert cp(s)==before
    r=p.Engine.restore(s.program,cp(s))
    for e in effects:s.ctx.attributes.value(a,'atk',effect=e);r.ctx.attributes.value(a,'atk',effect=e)
    assert cp(s)==cp(r)
def capture_pure():
    s=p.sim(p.joint_data()[0]);s.session.random.sample('existing_rng');p.ep(s,amount=19);s.ctx.attributes.value(p.refs(s)[1],'magic_resistance');before=cp(s);epoch=s.session.cache_epoch
    saved=s.session._capture_atomic();assert cp(s)==before and s.session.cache_epoch==epoch and saved['participants']
    assert 'participants' not in s.session.checkpoint()
def registration_guards():
    s=Session();s.register_atomic_participant('local',lambda:0,lambda saved:None)
    for args in [('local',lambda:0,lambda x:None),('bad',None,lambda x:None),('',lambda:0,lambda x:None)]:
        try:s.register_atomic_participant(*args)
        except (ValueError,TypeError):pass
        else:raise AssertionError('invalid participant registration accepted')
    with s.atomic():
        try:s.register_atomic_participant('late',lambda:0,lambda x:None)
        except RuntimeError:pass
        else:raise AssertionError('registration during atomic accepted')
    s.register_handler('probe',lambda session,payload: session.register_atomic_participant('during_advance',lambda:0,lambda x:None));s.schedule('probe',{},0)
    try:s.advance(1)
    except RuntimeError:pass
    else:raise AssertionError('registration during advance accepted')
    t=Session();t.register_atomic_participant('capture',lambda:t.register_atomic_participant('nested',lambda:0,lambda x:None),lambda x:None);before=t.checkpoint()
    try:
        with t.atomic():pass
    except RuntimeError:pass
    else:raise AssertionError('registration during capture accepted')
    assert t.checkpoint()==before and t._atomic_depth==0
def restore_hook_failure():
    s=Session();local={'value':5};restored=[]
    def bad(saved):raise RuntimeError('restore fault')
    s.register_atomic_participant('bad',lambda:None,bad)
    s.register_atomic_participant('good',lambda:local['value'],lambda saved:(local.update(value=saved),restored.append(True)))
    before=s.checkpoint();original=ValueError('primary body failure')
    try:
        with s.atomic():
            local['value']=77;s.world.create('temporary',{});s.emit('temporary',{});s.random.sample('temporary');s.schedule('pending',{},0);raise original
    except ValueError as caught:
        assert caught is original and caught.__cause__ is not None and 'restore fault' in str(caught.__cause__)
    else:raise AssertionError('primary exception lost')
    after=s.checkpoint();assert restored and local['value']==5
    for key in ('world','scheduler','events','random'):assert before[key]==after[key]
    assert after['failure']['atomic_restore_failure'] is True
    for action in (lambda:s.advance(1),lambda:s.atomic().__enter__()):
        try:action()
        except RuntimeError:pass
        else:raise AssertionError('incomplete derived rollback permitted execution')
    s.restore(before);assert not s._atomic_restore_failure
def public_gate_still_strict():
    s=p.sim(p.joint_data()[0]);p.ep(s,amount=19);s.ctx.attributes.value(p.refs(s)[1],'magic_resistance');before=cp(s)
    try:
        with s.session.atomic():s.ctx.attributes.value(p.refs(s)[1],'magic_resistance');raise ValueError('rollback')
    except ValueError:pass
    assert cp(s)==before
    altered=copy.deepcopy(before);row=altered['attribute_cache']['entries'][0];row['value']=999;row['record_digest']=p.digest({k:v for k,v in row.items() if k!='record_digest'})
    try:p.Engine.restore(s.program,altered)
    except ValueError:pass
    else:raise AssertionError('rollback weakened public cache validation')
def capture_mutation_rejected():
    for method in ('world','emit','random','schedule','commit','scheduler','event_log'):
        s=Session();before=s.checkpoint()
        operations={'world':lambda:s.world.create('temporary',{}),'emit':lambda:s.emit('temporary',{}),'random':lambda:s.random.sample('temporary'),'schedule':lambda:s.schedule('pending',{},0),'commit':lambda:s.commit([]),'scheduler':lambda:s.scheduler.reserve_sequence(),'event_log':lambda:s._events.emit('temporary',{},0)}
        s.register_atomic_participant('impure',operations[method],lambda saved:None)
        try:
            with s.atomic():raise AssertionError('body must not execute')
        except RuntimeError as error:assert 'cannot mutate kernel state' in str(error)
        else:raise AssertionError('impure capture accepted '+method)
        assert s.checkpoint()==before and s._atomic_depth==0 and not s._capturing_atomic
def all_writes_blocked_after_restore_hook_fault():
    s=p.sim();a,b=p.refs(s)
    s.session.register_atomic_participant('bad',lambda:0,lambda saved:(_ for _ in ()).throw(RuntimeError('restore hook')))
    before=s.session.checkpoint()
    try:
        with s.session.atomic():raise ValueError('body failure')
    except ValueError:pass
    failed=s.session.checkpoint();commands=copy.deepcopy(s._commands)
    operations=[lambda:s.session.commit([Intent('set',b,('runtime','probe'),1)]),lambda:s.session.schedule('probe',{},0),lambda:s.session.cancel(1),lambda:s.session.emit('probe',{}),lambda:s.ctx.set(b,('runtime','probe'),1),lambda:s.submit({'action':'withdraw','source':'src'}),lambda:s.session.world.create('probe',{}),lambda:s.session.world.set(b,('runtime','probe'),1),lambda:s.session.random.sample('probe')]
    for op in operations:
        try:op()
        except RuntimeError:pass
        else:raise AssertionError('public mutation bypassed fail-closed')
        assert s.session.checkpoint()==failed and s._commands==commands
    s.session.restore(before);assert not s.session._atomic_restore_failure
    s.ctx.set(b,('runtime','probe'),2);assert s.ctx.get(b,('runtime','probe'))==2
def restore_public_mutation_rejected():
    for operation in ('emit','schedule','world'):
        s=Session();before=s.checkpoint();original=ValueError('primary body failure')
        ops={'emit':lambda:s.emit('invalid',{}),'schedule':lambda:s.schedule('invalid',{},0),'world':lambda:s.world.create('invalid',{})}
        s.register_atomic_participant('bad',lambda:0,lambda saved:ops[operation]())
        try:
            with s.atomic():raise original
        except ValueError as error:
            assert error is original and 'restore callbacks cannot mutate' in str(error.__cause__)
        else:raise AssertionError('restore mutation allowed')
        after=s.checkpoint()
        for key in ('world','scheduler','events','random'):assert before[key]==after[key]
        assert after['failure']['atomic_restore_failure'] is True and not s._restoring_atomic
def original_cases():
    import pytest
    sys.path.insert(1,str(p.ROOT/'tests_v2'))
    exit_code=pytest.main([str(p.ROOT/'tests_v2/test_forced_distance.py'),str(p.ROOT/'tests_v2/test_kernel.py'),'-q','--basetemp','E:/ArkSimLogs/runs/c9_cache_atomic_own_v5_temp'])
    assert exit_code==0
def main():
    assert p.implementation_digest()==p.EXPECTED
    for name,fn in [('original_unchanged_forced_distance_and_kernel_files',original_cases),('nested_inner_rollback_outer_rollback_cause_and_cpp',nested_inner_then_outer),('historical_snapshot_identity_no_incarnation_borrow',historical_identity),('rule_override_equal_value_distinct_scope_restore',scope_rule_override),('capture_no_events_rng_jobs_id_consumption',capture_pure),('participant_registration_boundary_and_validation',registration_guards),('restore_hook_failure_primary_exception_and_fail_closed',restore_hook_failure),('public_tamper_gate_after_atomic_rollback',public_gate_still_strict),('capture_public_mutation_rejected_without_consumption',capture_mutation_rejected),('all_public_writes_blocked_after_hook_fault_restore_repairs',all_writes_blocked_after_restore_hook_fault),('restore_public_mutation_rejected_preserves_primary',restore_public_mutation_rejected)]:run(name,fn)
    report={'core':p.implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULTS) else 1,'results':RESULTS,'kernel_participants_scope':'trusted in-memory Session lifetime savepoints; hosts own any public persistence extension','original_test_sha256':hashlib.sha256((p.ROOT/'tests_v2/test_forced_distance.py').read_bytes()).hexdigest()}
    p.OUT.mkdir(parents=True,exist_ok=True);(p.OUT/'atomic.tests.v5.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
