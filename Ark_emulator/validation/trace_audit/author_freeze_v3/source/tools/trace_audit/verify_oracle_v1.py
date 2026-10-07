"""Independent known-value formulas and real-journal intermediate corruption."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v1 import audit,oracle
OUT=ROOT/'validation/trace_audit/oracle_tests_v1';BASE=ROOT/'validation/trace_audit/source_golden_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True);pins=json.loads((BASE/'oracle_pins.json').read_bytes())['rules'];source=BASE/'events.jsonl';gold=audit(source,pins);assert gold['source_formula_consistent'] and not gold['all_fields_independently_verified'];cases=[]
 for kind,defense,resistance,expected in [('physical',999,0,5.0),('arts',0,200,5.0),('arts',0,-50,100.0),('true',999,200,100)]:
  actual=oracle('rule/ark_standard_mitigation',{'power':100,'defense':defense,'resistance':resistance,'damage_type':kind},{'minimum_ratio':.05});assert actual==expected;cases.append({'case':'independent '+kind+' mitigation','expected':expected,'actual':actual})
 assert oracle('rule/ark_healing_power',{'attack':600,'scale':1.5,'additions':30},{})==930.0
 assert oracle('rule/ark_resource_bounds',{'candidate':1430.0,'capacity':1000,'bounds_parameters':{}},{})=={'value':1000,'overflow':430.0,'accepted':True}
 cases.append({'case':'heal power930 and cap1000 over430','passed':True})
 mutated=OUT/'intermediate_plus1_final_unchanged.jsonl';assert not mutated.exists();changed=False;sample=None;final_before={};final_after={}
 with source.open(encoding='utf8') as f,mutated.open('x',encoding='utf8',newline='') as out:
  for line in f:
   e=json.loads(line)
   if e['type']=='resource.changed':final_before[(e['payload']['target'],e['payload']['resource'])]=e['payload']['value']
   if not changed and e['type']=='calculation' and e['payload']['calculation_id']=='damage.pipeline':
    sample=deepcopy(e);before=deepcopy(e['payload']['value']);e['payload']['trace']['stages'][0]['trace']['raw']+=1;assert e['payload']['value']==before;changed=True
   if e['type']=='resource.changed':final_after[(e['payload']['target'],e['payload']['resource'])]=e['payload']['value']
   out.write(json.dumps(e,separators=(',',':'))+'\n')
 assert changed and final_before==final_after;bad=audit(mutated,pins);assert not bad['source_formula_consistent'] and any(e['field']=='nested.raw' for e in bad['failures']);cases.append({'case':'real middle nested raw+1 with all final resource events unchanged','rejected':True,'first_difference':bad['failures'][0],'mutated_journal_sha':sha(mutated)})
 tests=[('boolean_tick',lambda e:e.update(time=True)),('boolean_ID',lambda e:e.update(id=True)),('boolean_numeric_attack',lambda e:e['payload']['trace']['stages'][0]['trace']['inputs'].update(attack=True)),('boolean_numeric_output',lambda e:e['payload'].update(value=True)),('nonfinite_output',lambda e:e['payload']['trace'].update(value=float('inf')))]
 for name,change in tests:
  e=deepcopy(sample);change(e);path=OUT/(name+'.jsonl');assert not path.exists();path.write_text(json.dumps(e)+'\n',encoding='utf8',newline='');r=audit(path,pins);assert not r['source_formula_consistent'];cases.append({'case':name,'rejected':True,'difference':r['failures'][0]})
 unknown=deepcopy(sample);unknown['payload']['trace']['rule_fingerprint']='0'*64;path=OUT/'unknown_rule_fingerprint.jsonl';path.write_text(json.dumps(unknown)+'\n',encoding='utf8',newline='');r=audit(path,pins);assert not r['all_fields_independently_verified'] and r['pending_fields'];cases.append({'case':'unknown rule identity','status':'unverified','pending':r['pending_fields']})
 dest=OUT/'verification.json';assert not dest.exists();dest.write_text(json.dumps({'actual_exit':0,'source_journal_sha':sha(source),'pin_sha':sha(BASE/'oracle_pins.json'),'oracle_helper_sha':sha(ROOT/'tools/trace_audit/stream_oracle_v1.py'),'comparison_helper_sha':sha(ROOT/'tools/compare_campaign_trace.py'),'golden_audit':gold,'cases':cases,'client_verified':False,'no_unknown_rule_green':True},indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'cases':len(cases),'sha':sha(dest),'golden_counts':gold['counts']}))
if __name__=='__main__':main()
