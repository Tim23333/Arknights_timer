"""Known-value/source examples plus type and identity negatives for three added rules."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));OUT=ROOT/'validation/trace_audit/simple_formulas_v5'
from tools.trace_audit.stream_oracle_v5 import audit
from tools.trace_audit.stream_oracle_v5_math import oracle
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 examples=OUT/'actual_source_examples.jsonl';events=[json.loads(line) for line in examples.open()];pins=json.loads((OUT/'oracle_pins.json').read_bytes())['rules'];result=audit(examples,pins);assert result['source_formula_consistent'];cases=[]
 for seconds,expected in [(0.0,0),(1/30,1),(.1,3),(.16699999570846558,6),(1/30+1e-9,2)]:
  got=oracle('rule/ark_time_quantize',{'seconds':seconds,'quantum':1/30},{'ratio_digits':12});assert type(got) is int and got==expected;cases.append({'seconds':seconds,'expected_ticks':expected,'actual':got})
 assert oracle('rule/ark_ability_windup',{'timing_parameters':{'seconds':.16699999570846558}},{})==.16699999570846558
 assert oracle('rule/ark_deploy_refund',{'paid_cost':10.0,'refund_parameters':{'ratio':.5}},{})==5.0
 assert oracle('rule/ark_deploy_refund',{'paid_cost':40.0,'refund_parameters':{'ratio':.5,'raw_cost':10,'raw_cap_ratio':.5}},{})==5.0
 negatives=[]
 for index,e in enumerate(events):
  bad=deepcopy(e);bad['payload']['trace']['raw']+=1;file=OUT/('formula_'+str(index)+'_raw_plus1.jsonl');assert not file.exists();file.write_text(json.dumps(bad)+'\n',encoding='utf8',newline='');a=audit(file,pins);assert not a['source_formula_consistent'];negatives.append({'rule':e['payload']['rule_id'],'raw_plus1_rejected':True,'final_value_unchanged':bad['payload']['value']==e['payload']['value'],'failure':a['failures'][0]})
 quant=next(e for e in events if e['payload']['rule_id']=='rule/ark_time_quantize')
 for name,edit in [('quantum_boolean',lambda t:t['inputs'].update(quantum=True)),('seconds_boolean',lambda t:t['inputs'].update(seconds=False)),('ratio_digits_boolean',lambda t:t['parameters'].update(ratio_digits=True)),('quantum_zero',lambda t:t['inputs'].update(quantum=0)),('nonfinite_seconds',lambda t:t['inputs'].update(seconds=float('inf')))]:
  bad=deepcopy(quant);edit(bad['payload']['trace']);file=OUT/(name+'.jsonl');assert not file.exists();file.write_text(json.dumps(bad)+'\n',encoding='utf8',newline='');a=audit(file,pins);assert not a['source_formula_consistent'];negatives.append({'case':name,'rejected':True,'failure':a['failures'][0]})
 dest=OUT/'verification.json';assert not dest.exists();dest.write_text(json.dumps({'actual_exit':0,'known_value_quantization_cases':cases,'source_actual_examples_audit':result,'refund_examples':{'native_paid10_ratio_half':5.0,'repeat_paid40_capped_by_native_raw10_half':5.0},'negatives':negatives,'pins_sha':sha(OUT/'oracle_pins.json'),'source_examples_raw_sha':sha(examples),'helpers':[{str(ROOT/'tools/trace_audit'/name):sha(ROOT/'tools/trace_audit'/name)} for name in ('stream_oracle_v5.py','stream_oracle_v5_math.py','stream_oracle_v5_identity.py')],'independent_arithmetic_no_runtime_calculator':True,'numeric_full_acceptance':False,'client_verified':False},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'positive_quantization':len(cases),'negative_cases':len(negatives)}))
if __name__=='__main__':main()
