"""Separate reviewer tests for trace identity; preserve missing checks as failures."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.trace_audit.stream_oracle_v1 import audit


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    base = ROOT / 'validation/trace_audit/source_golden_v2'
    out = ROOT / 'validation/trace_audit/root_negative_review_v1'
    assert not out.exists()
    out.mkdir(parents=True)
    pinpath = base / 'oracle_pins.json'
    pins = json.loads(pinpath.read_bytes())['rules']
    source = base / 'events.jsonl'
    sample = None
    cached = None
    with source.open(encoding='utf8') as f:
        for line in f:
            e = json.loads(line)
            if sample is None and e['type'] == 'calculation' and e['payload']['calculation_id'] == 'damage.pipeline':
                sample = e
            if cached is None and e['type'] == 'calculation.cached':
                cached = e
            if sample is not None and cached is not None:
                break
    assert sample is not None and cached is not None
    mutations = [
        ('nested_contract_version', lambda e: e['payload']['trace']['stages'][0]['trace'].update(contract_version=999)),
        ('nested_contract_id', lambda e: e['payload']['trace']['stages'][0]['trace'].update(calculation_id='resource.cost')),
        ('nested_numeric_profile', lambda e: e['payload']['trace']['stages'][0]['trace'].update(numeric={'backend':'decimal','rounding':'floor'})),
        ('nested_trace_time', lambda e: e['payload']['trace']['stages'][0]['trace']['context'].update(time=e['time']+1)),
    ]
    results = []
    for name, mutate in mutations:
        event = deepcopy(sample)
        mutate(event)
        path = out / (name + '.jsonl')
        path.write_text(json.dumps(event)+'\n', encoding='utf8', newline='')
        result = audit(path, pins)
        detected = bool(result['failures'] or any('nested' in k for k in result['pending_fields']))
        results.append({'case':name, 'passed':detected, 'actual_audit':result, 'input_sha':sha(path),
                        'expected':'Changed nested identity must fail or become unverified, even when arithmetic and final values match'})
    helper = ROOT / 'tools/trace_audit/stream_oracle_v1.py'
    report = out / 'verification.json'
    report.write_text(json.dumps({'role':'Root independent identity counterexamples', 'passed':all(x['passed'] for x in results),
        'results':results, 'oracle_helper_sha':sha(helper), 'pins_sha':sha(pinpath), 'source_sha':sha(source),
        'scope':'Verifier review only; no runtime/content mutation or client approval'}, indent=2)+'\n', encoding='utf8', newline='')
    print(json.dumps({'passed':all(x['passed'] for x in results), 'results':[{'case':x['case'],'passed':x['passed']} for x in results], 'report_sha':sha(report)}))
    raise SystemExit(0 if all(x['passed'] for x in results) else 1)


if __name__ == '__main__':
    main()
