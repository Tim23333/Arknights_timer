import pytest
from tools.trace_audit.chapter08_stream_v2 import trace_check
def data():
 d={'id':'rule/peer/rate','kind':'rule','contract':'buff.lifetime_rate','parameters':{'attribute':'r','minimum':.01,'maximum':1},'implementation':{'type':'provider','provider':'reference.c8.dynamic_buff_rate'}};provider={'name':'reference.c8.dynamic_buff_rate','version':'1','source_sha256':'synthetic_policy_identity'};t={'rule_id':d['id'],'calculation_id':'buff.lifetime_rate','contract_version':1,'parameters':d['parameters'],'runtime_fingerprint':'runtime/peer','rule_fingerprint':'rule/peer','provider':provider,'inputs':{'attributes':{'r':.25},'clock':{'time':119,'quantum':1/30}},'context':{'time':119,'quantum':1/30,'seconds':119/30,'source_id':None,'target_id':None,'owner_id':None},'raw':4.0,'value':4.0,'numeric':{'backend':'float','rounding':'half_even'}};e={'type':'calculation','time':120,'payload':{'rule_id':d['id'],'calculation_id':d['contract'],'source':None,'target':None,'value':4.0}};return t,{d['id']:d},{d['id']:'rule/peer'},{d['implementation']['provider']:provider},e
def test_declared_boundary_previoussample_then_publication_nexttick():
 t,d,f,p,e=data();assert trace_check(t,d,f,p,'runtime/peer',event=e,expected_quantum=1/30)==4.0
@pytest.mark.parametrize('mutation',['plus2','inputclock','nonrateprovider','timeBool'])
def test_boundary_exception_not_general_relaxation(mutation):
 t,d,f,p,e=data()
 if mutation=='plus2':e['time']=121
 elif mutation=='inputclock':t['inputs']['clock']['time']=120
 elif mutation=='timeBool':t['context']['time']=True
 else:d[t['rule_id']]['contract']='field.trigger';t['calculation_id']='field.trigger';e['payload']['calculation_id']='field.trigger'
 with pytest.raises(AssertionError):trace_check(t,d,f,p,'runtime/peer',event=e,expected_quantum=1/30)
