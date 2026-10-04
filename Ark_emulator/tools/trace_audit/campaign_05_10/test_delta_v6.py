"""Real source quintet, unchanged final output mutations must lose verification."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from tools.trace_audit.stream_oracle_v6 import audit
ROOT=Path(__file__).resolve().parents[3]
BASE=[json.loads(line) for line in (ROOT/'validation/trace_audit/delta_only_v6/actual_five_events.jsonl').read_text(encoding='utf8').splitlines()]
PINS=json.loads((ROOT/'validation/trace_audit/simple_formulas_v5/oracle_pins.json').read_bytes())['rules']
def run(tmp_path,records):
 path=tmp_path/'actual.jsonl';path.write_text(''.join(json.dumps(e)+'\n' for e in records),encoding='utf8');return audit(path,PINS)
def test_real_before1_delta_minus1_bounds0_and_post_body0(tmp_path):
 r=run(tmp_path,BASE);assert not r['failures'];v=r['delta_only_resource_v6']['verified'];assert len(v)==1 and (v[0]['target'],v[0]['resource'],v[0]['before'],v[0]['delta'],v[0]['after'])==(25,'shield_charge',1,-1,0);assert r['all_fields_independently_verified'] is False
@pytest.mark.parametrize('mutation',['delta','source','target','resource','candidate','capacity','bounds_raw','bounds_value','bounds_context_owner','bounds_context_time','post_current','post_target','pre_current','bool_delta'])
def test_changed_intermediate_input_same_original_final_cannot_verify(tmp_path,mutation):
 records=deepcopy(BASE);change=next(e for e in records if e['id']==293333);bound=next(e for e in records if e['id']==293332);pre=next(e for e in records if e['id']==293316);post=next(e for e in records if e['id']==293334)
 if mutation in ('delta','source','target','resource'):change['payload'][mutation]={'delta':-2,'source':999,'target':999,'resource':'hp'}[mutation]
 if mutation in ('candidate','capacity'):bound['payload']['trace']['inputs'][mutation]+=1
 if mutation in ('bounds_raw','bounds_value'):bound['payload']['trace'][mutation.split('_')[1]]['value']=1
 if mutation=='bounds_context_owner':bound['payload']['trace']['context']['owner_id']=28
 if mutation=='bounds_context_time':bound['payload']['trace']['context']['time']+=1
 if mutation=='post_current':post['payload']['trace']['inputs']['resources']['shield_charge']['current']=1
 if mutation=='post_target':post['payload']['trace']['context']['target_id']=999
 if mutation=='pre_current':pre['payload']['trace']['inputs']['target']['components']['resources']['shield_charge']['current']=2
 if mutation=='bool_delta':change['payload']['delta']=False
 r=run(tmp_path,records);assert not r['delta_only_resource_v6']['verified'];assert r['failures'] or r['delta_only_resource_v6']['pending_fields']
@pytest.mark.parametrize('missing',['bounds','post','previous','before_body'])
def test_missing_source_input_witness_pending(tmp_path,missing):
 ids={'bounds':293332,'post':293334,'previous':288586,'before_body':293316};records=[e for e in BASE if e['id']!=ids[missing]];r=run(tmp_path,records);assert not r['delta_only_resource_v6']['verified'] and r['delta_only_resource_v6']['pending_fields']
def test_unknown_bounds_is_pending_not_formula_green(tmp_path):
 records=deepcopy(BASE);bound=next(e for e in records if e['id']==293332);bound['payload']['rule_id']=bound['payload']['trace']['rule_id']='rule/user/custom_bounds';r=run(tmp_path,records);assert not r['delta_only_resource_v6']['verified'] and r['delta_only_resource_v6']['pending_fields']
