"""Typed actual wrapper golden plus middle-only corruption negatives, no tolerance."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/wrapper_tests_v4';sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v4 import audit
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);source=ROOT/'validation/trace_audit/chen_wrapper_golden_v4/actual_selected_events.jsonl';events=[json.loads(line) for line in source.open()];sample=events[1];pinsfile=ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json';pins=json.loads(pinsfile.read_bytes())['rules'];positive=audit(source,pins);assert positive['source_formula_consistent'] and positive['aggregate_provider_calls_checked']==2
 def callback(e):return next(n for n in e['payload']['trace']['stages'] if n.get('kind')=='calculation')
 def provider(e):return next(n for n in e['payload']['trace']['stages'] if n.get('kind')=='provider')
 cases=[('callback_child_raw_plus1',lambda e:callback(e)['trace'].update(raw=callback(e)['trace']['raw']+1)),('callback_value_plus1',lambda e:callback(e).update(value=callback(e)['value']+1)),('callback_kind_removed',lambda e:callback(e).pop('kind')),('callback_fabricated_wrapper_raw',lambda e:callback(e).update(raw=callback(e)['trace']['raw'])),('aggregate_raw_ratio_plus1',lambda e:provider(e)['raw'].update(ratio=provider(e)['raw']['ratio']+1)),('callback_source_rule_identity',lambda e:callback(e).update(rule_id='rule/not_the_called_rule'))];results=[]
 for name,mutate in cases:
  e=deepcopy(sample);final_before=deepcopy(e['payload']['value']);mutate(e);assert e['payload']['value']==final_before;file=OUT/(name+'.jsonl');file.write_text(json.dumps(e)+'\n',encoding='utf8',newline='');r=audit(file,pins);assert not r['source_formula_consistent'] or r['pending_fields'];results.append({'case':name,'middle_only_final_unchanged':True,'rejected_or_unverified':True,'failures':r['failures'],'pending':r['pending_fields'],'input_sha':sha(file)})
 graph=None
 with (ROOT/'validation/trace_audit/source_golden_v3/events.jsonl').open() as f:
  for line in f:
   e=json.loads(line)
   if e['type']=='calculation' and e['payload']['calculation_id']=='damage.pipeline':graph=e;break
 assert graph is not None;graph['payload']['trace']['stages'][0].pop('raw');file=OUT/'graph_wrapper_raw_missing.jsonl';file.write_text(json.dumps(graph)+'\n',encoding='utf8',newline='');r=audit(file,pins);assert not r['source_formula_consistent'];results.append({'case':'graph_wrapper_raw_missing','rejected':True,'failures':r['failures']})
 dest=OUT/'verification.json';dest.write_text(json.dumps({'actual_exit':0,'source_raw_golden_sha':sha(source),'pins_sha':sha(pinsfile),'helpers':[{'path':str(ROOT/'tools/trace_audit'/name),'sha':sha(ROOT/'tools/trace_audit'/name)} for name in ('stream_oracle_v4.py','stream_oracle_v4_math.py','stream_oracle_v4_identity.py')],'positive_actual_chen':positive,'negatives':results,'cases':len(results),'client_verified':False,'no_uniform_numeric_tolerance':True},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'negative_cases':len(results),'positive_typed_calls':positive['aggregate_provider_calls_checked']}))
if __name__=='__main__':main()
