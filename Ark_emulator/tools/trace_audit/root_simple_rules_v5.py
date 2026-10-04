"""Independent fixed expected values and real trace-input corruption for new rules."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v5_math import oracle
from tools.trace_audit.stream_oracle_v5 import audit


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base=ROOT/'validation/trace_audit/simple_formulas_v5';pins=json.loads((base/'oracle_pins.json').read_bytes())['rules']
    out=ROOT/'validation/trace_audit/root_simple_rules_v5';assert not out.exists();out.mkdir(parents=True);results=[]
    for seconds,expected in [(1.0,30),(.3333333333333333,10),(.04,2),(.0333333333333333,1),(.033333333334,2)]:
        actual=oracle('rule/ark_time_quantize',{'seconds':seconds,'quantum':1/30},{'ratio_digits':12})
        assert type(actual) is int and actual==expected
        results.append({'case':'quantization','seconds':seconds,'expected':expected,'actual':actual})
    assert oracle('rule/ark_ability_windup',{'timing_parameters':{'seconds':.4}},{})==.4
    results.append({'case':'windup configured0.4','passed':True})
    for paid,params,expected in [(25,{'ratio':.2},5.0),(40,{'ratio':.5,'raw_cost':14,'raw_cap_ratio':.5},7.0)]:
        actual=oracle('rule/ark_deploy_refund',{'paid_cost':paid,'refund_parameters':params},{})
        assert actual==expected;results.append({'case':'refund','actual':actual,'expected':expected})
    events=[json.loads(line) for line in (base/'actual_source_examples.jsonl').read_text(encoding='utf8').splitlines()]
    mutations={'rule/ark_time_quantize':lambda t:t['inputs'].update(seconds=t['inputs']['seconds']+1),
               'rule/ark_ability_windup':lambda t:t['inputs']['timing_parameters'].update(seconds=t['inputs']['timing_parameters']['seconds']+1),
               'rule/ark_deploy_refund':lambda t:t['inputs']['refund_parameters'].update(ratio=0)}
    for e in events:
        rid=e['payload']['rule_id'];before=deepcopy(e['payload']['value']);mutations[rid](e['payload']['trace'])
        assert e['payload']['value']==before
        path=out/(rid.replace('/','_')+'.mutated.jsonl');path.write_text(json.dumps(e)+'\n',encoding='utf8',newline='')
        result=audit(path,pins);assert result['failures'] and not result['source_formula_consistent']
        results.append({'case':'actual_input_changed_same_output','rule':rid,'rejected':True,'first_difference':result['failures'][0]})
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump({'passed':True,'cases':results,'pin_sha':sha(base/'oracle_pins.json'),
        'oracle_sources':{str(p):sha(p) for p in [ROOT/'tools/trace_audit/stream_oracle_v5.py',ROOT/'tools/trace_audit/stream_oracle_v5_math.py',ROOT/'tools/trace_audit/stream_oracle_v5_identity.py']},
        'scope':'Independent extra literals and actual input mutations, source formula subset only; not full intermediate/client approval'},f,indent=2)
    print(json.dumps({'passed':True,'cases':len(results),'sha':sha(target)}))


if __name__=='__main__':main()
