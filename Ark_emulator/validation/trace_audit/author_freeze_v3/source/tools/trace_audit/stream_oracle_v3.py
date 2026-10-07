"""V3 adds standard graph call-context/binding inheritance, leaving V1/V2 frozen."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v2 import audit as parent_audit,STANDARD,STANDARD_SHA
from tools.compare_campaign_trace import exact
CONTRACTS=STANDARD.parents[2]/'rules/contracts.json'
def audit(path,pins,max_events=None):
 result=parent_audit(path,pins,max_events);failures=[];checked=0;count=0
 def fail(e,field,want,actual):
  if len(failures)<50:failures.append({'event':e['id'],'time':e['time'],'field':field,'reason':'Standard damage graph call-context/binding inheritance differs','expected':want,'actual':actual})
 with Path(path).open(encoding='utf8') as f:
  for line in f:
   try:e=json.loads(line)
   except ValueError:continue
   count+=1;v=e.get('payload',{});t=v.get('trace',{})
   if e.get('type')=='calculation' and t.get('rule_id')=='rule/ark_damage_pipeline' and t.get('rule_fingerprint')==pins.get('rule/ark_damage_pipeline',{}).get('rule_fingerprint'):
    ctx=t.get('context',{})
    for key,parent in [('source_id',v.get('source')),('target_id',v.get('target'))]:
     if not exact(parent,ctx.get(key)):fail(e,'graph.parent.context.'+key,parent,ctx.get(key))
    for node in t.get('stages',[]):
     child=node.get('trace',{});name=node.get('id');expected_owner={'power':'source','mitigation':'target'}.get(name)
     if expected_owner is None:continue
     for key in ('source_id','target_id','owner_id','time','seconds','quantum','rule_scope'):
      if not exact(ctx.get(key),child.get('context',{}).get(key)):fail(e,'graph.'+name+'.context.'+key,ctx.get(key),child.get('context',{}).get(key))
     if not exact(t.get('runtime_fingerprint'),child.get('runtime_fingerprint')):fail(e,'graph.'+name+'.runtime_fingerprint',t.get('runtime_fingerprint'),child.get('runtime_fingerprint'))
     binding=child.get('binding',{})
     if not exact(expected_owner,binding.get('owner')):fail(e,'graph.'+name+'.binding.owner',expected_owner,binding.get('owner'))
     overrides=binding.get('overrides',[])
     if not overrides or not exact(child.get('rule_id'),overrides[-1].get('rule_id')):fail(e,'graph.'+name+'.binding.selected_rule',child.get('rule_id'),overrides[-1].get('rule_id') if overrides else None)
     if overrides and not exact(binding.get('origin'),overrides[-1].get('scope')):fail(e,'graph.'+name+'.binding.origin',overrides[-1].get('scope'),binding.get('origin'))
     checked+=1
   if max_events and count>=max_events:break
 result['schema']='ark-sim/source-formula-stream-audit/v3';result['graph_context_calls_checked']=checked;result['failures']+=failures;result['source_formula_consistent']=not result['failures'];result['all_fields_independently_verified']=not result['failures'] and not result['pending_fields'];result['graph_context_contract']='Only reviewed rule/ark_damage_pipeline: same context actor IDs/owner/time/quantum/scope/runtime inherited for power and mitigation, with contract owner source/target respectively. Other/custom graph call scopes remain unverified.';return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--journal',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-events',type=int);a=p.parse_args();assert not a.output.exists();r=audit(a.journal,json.loads(a.pins.read_bytes())['rules'],a.max_events);r['journal']=str(a.journal);r['pins_sha']=hashlib.sha256(a.pins.read_bytes()).hexdigest();r['helper_sha']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'failures':r['failures'][:4],'graph_checked':r['graph_context_calls_checked'],'identity_counts':r['identity_counts']}));raise SystemExit(0 if r['source_formula_consistent'] else 1)
if __name__=='__main__':main()
