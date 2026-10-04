"""Actual3992 shield packet and subsequent zerochange ledger, negative controls."""
import json
from pathlib import Path
from copy import deepcopy
import pytest
from tools.trace_audit.stream_oracle_v7 import audit
ROOT=Path(__file__).resolve().parents[2]
BASE=[json.loads(x) for x in (ROOT/'validation/trace_audit/07-17_delta_bound_v7/golden.jsonl').read_text(encoding='utf8').splitlines()]
PINS=json.loads((ROOT/'validation/trace_audit/simple_formulas_v5/oracle_pins.json').read_bytes())['rules']
W=json.loads((ROOT/'validation/trace_audit/07-17_delta_bound_v7/input_witness_pins.json').read_bytes())

def run(tmp_path,rows):
    p=tmp_path/'events.jsonl';p.write_text(''.join(json.dumps(e)+'\n' for e in rows),encoding='utf8');return audit(p,PINS,W)

def test_actual_shield1_minus1_to0_followed_delta0_is_strictly_verified(tmp_path):
    r=run(tmp_path,BASE);assert not r['failures']
    assert len(r['delta_only_resource_v7']['verified'])==1
    v=r['delta_only_resource_v7']['verified'][0];assert (v['before'],v['delta'],v['after'])==(1,-1,0)
    assert r['corrected_resource_ledger']['verified']==1
    assert len(r['superseded_verifier_failures'])==2

@pytest.mark.parametrize('mutation',['delta','before','bounds','post','runtime','subsequentdelta','subsequentvalue','subsequentparams','booldelta'])
def test_changed_intermediate_fields_never_supercede_as_pass(tmp_path,mutation):
    rows=deepcopy(BASE);by={e['id']:e for e in rows}
    if mutation=='delta':by[647977]['payload']['delta']=-2
    if mutation=='before':by[647960]['payload']['trace']['inputs']['target']['components']['resources']['shield_charge']['current']=2
    if mutation=='bounds':by[647976]['payload']['trace']['inputs']['candidate']=1
    if mutation=='post':by[647978]['payload']['trace']['inputs']['resources']['shield_charge']['current']=1
    if mutation=='runtime':by[647976]['payload']['trace']['runtime_fingerprint']='foreign'
    if mutation=='subsequentdelta':by[707555]['payload']['delta']=1
    if mutation=='subsequentvalue':by[707555]['payload']['value']=1
    if mutation=='subsequentparams':by[707554]['payload']['trace']['parameters']={'foreign':1}
    if mutation=='booldelta':by[647977]['payload']['delta']=False
    r=run(tmp_path,rows);assert r['failures'] or r['delta_only_resource_v7']['pending_fields']
