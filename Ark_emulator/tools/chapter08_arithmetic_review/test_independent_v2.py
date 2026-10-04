import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'));sys.path.insert(1,str(ROOT))
from tools.trace_audit.chapter08_arithmetic_v2 import expected
from tools.trace_audit.chapter08_stream_v2 import trace_check,supported
def definition(provider=None,expression=None,params=None):return {'id':'rule/independent/literal','kind':'rule','parameters':params or {},'implementation':{'type':'provider','provider':provider} if provider else {'type':'expression','expression':expression}}
@pytest.mark.parametrize('expression,field',[('inputs.timing_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)','timing_parameters'),('inputs.duration_parameters.seconds/max(inputs.attributes.attack_speed_ratio,.01)','duration_parameters')])
def test_ASPD_below_point01_literal_clamp6_seconds(expression,field):assert expected(definition(expression=expression),{'attributes':{'attack_speed_ratio':.003},field:{'seconds':.06}},{})==6.0
def test_delayed_recovery_uses_max_delay_not_shorter_duration_literal_half_second():
 d=definition('reference.c8.talula.start_cooldown',params={'mapping_speed':1.2,'source_duration':.3,'source_delay':.9});assert expected(d,{'attributes':{'attack_speed_ratio':1.5},'recovery_parameters':{'seconds':1}},{'quantum':1/30})==.5
def test_burn_missing_parent_and_duplicate_child_do_not_green_damage():
 d=definition('reference.c8.dragon_fire.pipeline',params={'timer':'parent','child':'child','base':81,'addition':145,'increase_duration':12});child={'definition':'child','started_at':0,'expires_at':None};ctx={'time':120,'quantum':1/60};inp={'target':{'components':{'buffs':{'instances':[child]}}}};assert expected(d,inp,ctx)=={'accepted':False,'amount':0,'allocations':[],'events':[]};inp['target']['components']['buffs']['instances']=[{'definition':'parent','expires_at':None},child,deepcopy(child)];assert expected(d,inp,ctx)=={'accepted':False,'amount':0,'allocations':[],'events':[]}
@pytest.mark.parametrize('provider,inputs,context,params',[('reference.c8.dynamic_buff_rate',{'attributes':{'r':True}},{},{'attribute':'r','minimum':.01,'maximum':1}),('model.field.uniform_trigger',{'blackboard':{'lo':8,'hi':12},'samples':[{'value':False}]},{},{'minimum_key':'lo','maximum_key':'hi'}),('reference.c8.bsnake.skills.recovery',{'attributes':{'attack_speed_ratio':True},'recovery_parameters':{'seconds':1}},{'quantum':1/30},{'full_seconds':.7})])
def test_typed_Bool_numeric_inputs_reject(provider,inputs,context,params):
 with pytest.raises(ValueError):expected(definition(provider,params=params),inputs,context)

def actual():
 data=json.loads((ROOT/'validation/trace_audit/chapter08_arithmetic_independent_v1/actual_source_compact.json').read_bytes());return deepcopy(data['trace']),data['definitions'],data['rule_fingerprints'],data['provider_identities'],data['runtime']
@pytest.mark.parametrize('field',['raw','value','rule_fingerprint','runtime_fingerprint','parameters','numeric'])
def test_real_source_trace_scalar_and_identity_mutations_rejected(field):
 t,d,f,p,r=actual()
 if field in ('raw','value'):t[field]=99999
 elif field in ('rule_fingerprint','runtime_fingerprint'):t[field]='0'*64
 elif field=='parameters':t[field]['injected']=True
 else:t[field]={'backend':'decimal','rounding':'floor'}
 with pytest.raises((AssertionError,ValueError,KeyError)):trace_check(t,d,f,p,r,expected_quantum=1/30)
@pytest.mark.parametrize('field',['contract_version','calculation_id','context_time_bool'])
def test_real_trace_contract_calculation_and_typed_time_forgery_must_reject(field):
 t,d,f,p,r=actual()
 if field=='contract_version':t['contract_version']=999
 elif field=='calculation_id':t['calculation_id']='resource.cost'
 else:
  # First observed uniform clock is atzero; boolFalse would equal0 but has wrong shape.
  assert t['context']['time']==0;t['context']['time']=False
 with pytest.raises((AssertionError,ValueError,KeyError)):trace_check(t,d,f,p,r,expected_quantum=1/30)
