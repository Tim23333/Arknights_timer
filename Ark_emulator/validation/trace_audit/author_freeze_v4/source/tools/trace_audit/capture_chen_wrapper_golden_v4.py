"""Actual native Chen frame780/SP0/ATK659.4 and DEF407.40000000000003 wrappers."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/trace_audit/chen_wrapper_golden_v4';sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v4 import audit
from tools.compare_campaign_trace import exact
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir(parents=True);cp=Path('E:/ArkSimEvidence/campaign/05_09_8fa4e36752e92f7d/public_v1.checkpoint.json');d=json.loads(cp.read_bytes());ref=d['kernel']['events']['reference'];source=Path(ref['path']);assert sha(source)==ref['sha256'];selected=[];file=OUT/'actual_selected_events.jsonl';ids={175558,175641,175642}
 with source.open('rb') as f,file.open('xb') as out:
  for line in f:
   e=json.loads(line)
   if e['id'] in ids:out.write(line);selected.append(e)
 assert {e['id'] for e in selected}==ids;sp=selected[0];assert sp['time']==780 and sp['payload']['resource']=='sp' and sp['payload']['target']==12 and sp['payload']['value']==0
 expected={'atk':(628+0)*(1+.05)*1,'def':(388+0)*(1+.05)*1};results=[]
 for e in selected[1:]:
  t=e['payload']['trace'];attr=t['context']['attribute'];assert t['context']['time']==780 and t['context']['seconds']==780*(1/30) and t['context']['source_id']==12;assert exact(t['raw'],expected[attr]) and exact(t['value'],expected[attr]);call=next(n for n in t['stages'] if n.get('kind')=='calculation');assert 'raw' not in call and call['trace']['raw']==expected[attr] and call['trace']['value']==call['value']==expected[attr];results.append({'event':e['id'],'attribute':attr,'expected_exact_float_operation_result':expected[attr],'actual':t['value'],'callback_keys':sorted(call),'frame':780,'seconds':26.0})
 pinfile=ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json';r=audit(file,json.loads(pinfile.read_bytes())['rules']);assert r['source_formula_consistent'];report={'actual_exit':0,'source_CP_sha':sha(cp),'complete_CP_journal_reference':ref,'complete_CP_journal_SHA_verified':True,'selected_raw_line_sha':sha(file),'selected_raw_lines_unmodified':True,'actual_SP_frame_event':sp,'expected_operations':'(base+0)*(1+sum(value*stacks))*1; exact float result, no invented tolerance','normal_actual_wrappers':results,'audit':r,'pins_sha':sha(pinfile),'source_numeric_full_acceptance':False,'client_verified':False};dest=OUT/'verification.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(dest),'exact_expected':expected,'audit_failures':r['failures']}))
if __name__=='__main__':main()
