"""Independent actual cache and parent-child trace source identity counterexamples."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v2 import audit


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base=ROOT/'validation/trace_audit/source_golden_v3'
    pinpath=ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json'
    pins=json.loads(pinpath.read_bytes())['rules']
    rows=[];sample=None;cached=None
    with (base/'events.jsonl').open(encoding='utf8') as f:
        for line in f:
            e=json.loads(line);rows.append(e)
            if sample is None and e['type']=='calculation' and e['payload']['calculation_id']=='damage.pipeline':sample=deepcopy(e)
            if cached is None and e['type']=='calculation.cached':cached=deepcopy(e)
            if sample and cached:break
    assert sample and cached
    out=ROOT/'validation/trace_audit/root_binding_review_v2';assert not out.exists();out.mkdir(parents=True)
    results=[]
    mutations=[('cached_wrong_owner',cached,lambda e:e['payload'].update(owner=9999)),
               ('cached_wrong_attribute',cached,lambda e:e['payload'].update(attribute='atk')),
               ('cached_wrong_contract',cached,lambda e:e['payload'].update(calculation_id='resource.cost')),
               ('nested_wrong_source',sample,lambda e:e['payload']['trace']['stages'][0]['trace']['context'].update(source_id=9999)),
               ('nested_wrong_target',sample,lambda e:e['payload']['trace']['stages'][1]['trace']['context'].update(target_id=9999))]
    for name,target,mutate in mutations:
        candidate=[]
        for row in rows:
            e=deepcopy(row)
            if e['id']==target['id']:mutate(e)
            candidate.append(e)
        path=out/(name+'.jsonl')
        with path.open('x',encoding='utf8',newline='') as f:
            for e in candidate:f.write(json.dumps(e)+'\n')
        result=audit(path,pins)
        passed=bool(result['failures'])
        results.append({'case':name,'passed':passed,'audit':result,'input_sha':sha(path),
                        'expected':'Same numerical value does not excuse different source/target/attribute/contract identity'})
    target=out/'verification.json'
    target.write_text(json.dumps({'passed':all(x['passed'] for x in results),'results':results,
        'helper_sha':sha(ROOT/'tools/trace_audit/stream_oracle_v2.py'),'scope':'Independent source binding review; preserve failure if uncovered'},indent=2)+'\n',encoding='utf8',newline='')
    print(json.dumps({'passed':all(x['passed'] for x in results),'results':[{'case':x['case'],'passed':x['passed']} for x in results],'sha':sha(target)}))
    raise SystemExit(0 if all(x['passed'] for x in results) else 1)


if __name__=='__main__':main()
