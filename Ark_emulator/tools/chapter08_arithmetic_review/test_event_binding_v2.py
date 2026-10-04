import pytest
from copy import deepcopy
from tools.chapter08_arithmetic_review.test_independent_v2 import actual,trace_check
def event(trace):return {'id':73,'time':trace['context']['time'],'type':'calculation','payload':{'calculation_id':trace['calculation_id'],'rule_id':trace['rule_id'],'value':deepcopy(trace['value']),'source':trace['context']['source_id'],'target':trace['context']['target_id'],'trace':trace}}
def test_actual_compact_trace_event_binding_accepts():
 t,d,f,p,r=actual();assert trace_check(t,d,f,p,r,event=event(t),expected_quantum=1/30)==t['value']
@pytest.mark.parametrize('field',['event_time','event_timeBool','event_calculation','event_rule','event_value','event_actorBool','quantum_coherent','seconds','context_ownerBool'])
def test_event_clock_identity_bindings_fail_even_with_unchanged_numeric_output(field):
 t,d,f,p,r=actual();e=event(t)
 if field=='event_time':e['time']+=1
 elif field=='event_timeBool':e['time']=False
 elif field=='event_calculation':e['payload']['calculation_id']='resource.cost'
 elif field=='event_rule':e['payload']['rule_id']='rule/foreign'
 elif field=='event_value':e['payload']['value']={'enabled':True,'next_delay_seconds':123}
 elif field=='event_actorBool':e['payload']['source']=False
 elif field=='quantum_coherent':t['context']['quantum']=1/60;t['context']['seconds']=t['context']['time']/60
 elif field=='seconds':t['context']['seconds']=1
 else:t['context']['owner_id']=False
 with pytest.raises(AssertionError):trace_check(t,d,f,p,r,event=e,expected_quantum=1/30)
