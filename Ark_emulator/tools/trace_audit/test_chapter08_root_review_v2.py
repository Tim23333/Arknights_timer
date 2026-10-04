"""Root review of strict temporal/contract identity with fresh fixture values."""
from copy import deepcopy

import pytest
from tools.trace_audit.chapter08_stream_v2 import trace_check


def fixture():
    definition={'id':'rule/root/rate','kind':'rule','contract':'buff.lifetime_rate',
        'parameters':{'attribute':'ratio','minimum':.001,'maximum':1000},
        'implementation':{'type':'provider','provider':'reference.c8.dynamic_buff_rate'}}
    provider={'name':'reference.c8.dynamic_buff_rate','source_sha256':'root_synthetic_bound_identity'}
    trace={'calculation_id':'buff.lifetime_rate','contract_version':1,'rule_id':definition['id'],
        'rule_fingerprint':'root_rule','runtime_fingerprint':'root_runtime','provider':deepcopy(provider),
        'parameters':deepcopy(definition['parameters']),'inputs':{'attributes':{'ratio':.2},'clock':{'time':300,'quantum':.02}},
        'context':{'time':300,'seconds':6.0,'quantum':.02,'source_id':17,'target_id':23,'owner_id':23},
        'raw':5.0,'value':5.0,'numeric':{'backend':'float','rounding':'half_even'}}
    event={'id':41,'type':'calculation','time':301,'payload':{'calculation_id':'buff.lifetime_rate',
        'rule_id':definition['id'],'value':5.0,'source':17,'target':23}}
    return trace,{definition['id']:definition},{definition['id']:'root_rule'},{provider['name']:provider},event


def test_fresh_quantum_point02_rate5_previous300_to301_event():
    trace,defs,pins,providers,event=fixture()
    assert trace_check(trace,defs,pins,providers,'root_runtime',event=event,expected_quantum=.02)==5


@pytest.mark.parametrize('mutation',[
    lambda trace,event:trace.update(contract_version=True),
    lambda trace,event:trace.update(calculation_id='buff.duration'),
    lambda trace,event:trace['context'].update(time=300.0),
    lambda trace,event:trace['context'].update(target_id=False),
    lambda trace,event:event.update(time=302),
    lambda trace,event:event['payload'].update(target=24),
    lambda trace,event:trace['inputs']['clock'].update(time=301),
])
def test_fresh_clock_and_identity_mutations_reject_unchanged_value(mutation):
    trace,defs,pins,providers,event=fixture();mutation(trace,event)
    assert trace['value']==5.0
    with pytest.raises(AssertionError):
        trace_check(trace,defs,pins,providers,'root_runtime',event=event,expected_quantum=.02)
