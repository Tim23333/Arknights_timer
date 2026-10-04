import sys,json,hashlib,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import pytest
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 helpers=[ROOT/'tools/trace_audit'/n for n in ['chapter08_arithmetic_v1.py','chapter08_stream_v1.py','chapter08_prefix_v2.py','chapter08_arithmetic_v2.py','chapter08_stream_v2.py','chapter08_prefix_v3.py']]+list(Path(__file__).parent.glob('*.py'));fixture=ROOT/'validation/trace_audit/chapter08_arithmetic_independent_v1/actual_source_compact.json';paths=helpers+[fixture,ROOT/'validation/trace_audit/chapter08_native_prefix_v2/verification.json',ROOT/'validation/trace_audit/chapter08_native_prefix_v3/verification.json'];before={str(p):sha(p) for p in paths};data=json.loads(fixture.read_bytes());from tools.trace_audit.chapter08_stream_v1 import trace_check as old;leaks=[]
 for field in ['contract_version','calculation_id','context_time_bool']:
  t=deepcopy(data['trace'])
  if field=='contract_version':t[field]=999
  elif field=='calculation_id':t[field]='resource.cost'
  else:t['context']['time']=False
  result=old(t,data['definitions'],data['rule_fingerprints'],data['provider_identities'],data['runtime']);leaks.append({'mutated_field':field,'old_accepted':True,'same_value':result==data['trace']['value'],'mutated_trace':t})
 cases=[];start=time.monotonic()
 class Capture:
  def pytest_runtest_logreport(self,report):
   if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'failure':str(report.longrepr) if report.failed else None})
 code=pytest.main([str(Path(__file__).with_name(n)) for n in ['test_independent_v2.py','test_event_binding_v2.py','test_temporal_v2.py','test_pending_v2.py']]+['-q','--tb=short','--import-mode=importlib'],plugins=[Capture()]);after={str(p):sha(p) for p in paths};assert before==after;out=ROOT/'validation/trace_audit/chapter08_arithmetic_independent_v2';out.mkdir(exist_ok=False);f=out/'verification.json';f.write_text(json.dumps({'passed':code==0,'actual_exit':code,'cases':cases,'elapsed':time.monotonic()-start,'source_before':before,'source_after':after,'original_v1_actual_binding_failures':leaks,'scope':'Original16 independentdifferent literals/realcompactsource identity assertions nowpass unchangedexpected; addedclock/quantum/event/actor typedbinding rejects and temporal sourcebuff.lifetime_rate priorinterval+nextboundary publication only. Unknowncustomnumeric/expression pending; cached calculations pending notgreen. Independentformula only, no runtimesamecalculator reused. Smallactual5.7KB fixture compiledbeforecleanup sourceFP/runtime retained. Originalv2 Prefix9bb historicalsubset notmigrated. Prefixv3 b0ae incorrect sameeventtime gate failed195 legitimate temporal traces retained asoraclefailure; its raw checkpoint/prefix cleanup completed. Newfixed tools not rerun deleted prefixes; no fakepass and no largejournal dependence.'},indent=2),encoding='utf8');print(json.dumps({'actual_exit':code,'cases':len(cases),'sha':sha(f),'bytes':f.stat().st_size}));raise SystemExit(code)
if __name__=='__main__':main()
