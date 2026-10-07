"""V4 uses source-typed callback/graph wrappers; all old audit versions remain frozen."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit.stream_oracle_v4_identity import audit as parent_audit,STANDARD,STANDARD_SHA
from tools.trace_audit.stream_oracle_v4_math import number
from tools.compare_campaign_trace import exact
CONTRACTS=STANDARD.parents[2]/'rules/contracts.json'
def audit(path,pins,max_events=None):
 result=parent_audit(path,pins,max_events);failures=[];checked=0;count=0
 aggregate_checked=0
 def fail(e,field,want,actual):
  if len(failures)<50:failures.append({'event':e['id'],'time':e['time'],'field':field,'reason':'Standard damage graph call-context/binding inheritance differs','expected':want,'actual':actual})
 with Path(path).open(encoding='utf8') as f:
  for line in f:
   try:e=json.loads(line)
   except ValueError:continue
   count+=1;v=e.get('payload',{});t=v.get('trace',{})
   if e.get('type')=='calculation' and t.get('rule_id')=='rule/ark_attribute_layers' and t.get('rule_fingerprint')==pins.get('rule/ark_attribute_layers',{}).get('rule_fingerprint'):
    import math
    aggregations=[]
    for node in t.get('stages',[]):
     if node.get('kind')=='provider':
      expected_provider={'name':'ark.attributes.aggregate','module':'ark_sim.presets.providers','qualname':'aggregate_layer','version':'ark-preset/1','source_sha256':'32a1f39f95d13591a779bcaa73a20c49594059ad03c075286ee2e9f03abe3342','descriptor':{'version':'ark-preset/1','time_dependency':'static'}}
      if node.get('provider')!=expected_provider or set(node)!={'id','kind','provider','inputs','parameters','raw','value','stages'}:
       result['pending_fields']['provider.aggregate.wrapper_or_descriptor_unreviewed']=result['pending_fields'].get('provider.aggregate.wrapper_or_descriptor_unreviewed',0)+1;continue
      inputs=node['inputs'];op=node['parameters'].get('operation');values=[number(m['value'])*number(m.get('stacks',1)) for m in inputs['modifiers']];want={'additive':0,'ratio':0,'factor':1}
      if op=='add':want['additive']=sum(values)
      elif op=='ratio_sum':want['ratio']=sum(values)
      elif op=='ratio_product':want['factor']=math.prod(1+x for x in values)
      elif op=='factor_product':want['factor']=math.prod(values)
      else:result['pending_fields']['provider.aggregate.operation_unreviewed']=result['pending_fields'].get('provider.aggregate.operation_unreviewed',0)+1;continue
      for field in ('raw','value'):
       if not exact(want,node[field]):fail(e,'provider.aggregate.'+field,want,node[field])
      selected=[m for m in t['inputs']['modifier_layers'] if m.get('layer','flat')==inputs['layer']]
      if not exact(selected,inputs['modifiers']):fail(e,'provider.aggregate.inputs.modifiers',selected,inputs['modifiers'])
      expected_op=t['parameters']['operations'].get(inputs['layer'])
      if not exact(expected_op,op):fail(e,'provider.aggregate.parameters.operation',expected_op,op)
      aggregations.append(want);aggregate_checked+=1
     elif node.get('kind')=='calculation' and node.get('calculation_id')=='attributes.modifier_layer' and aggregations:
      actual=node.get('trace',{}).get('inputs',{}).get('layer_parameters');want=aggregations.pop(0)
      if not exact(want,actual):fail(e,'callback.inputs.layer_parameters',want,actual)
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
 result['schema']='ark-sim/source-formula-stream-audit/v4';result['graph_context_calls_checked']=checked;result['aggregate_provider_calls_checked']=aggregate_checked;result['failures']+=failures;result['source_formula_consistent']=not result['failures'];result['all_fields_independently_verified']=not result['failures'] and not result['pending_fields'];result['graph_context_contract']='Only reviewed rule/ark_damage_pipeline: same context actor IDs/owner/time/quantum/scope/runtime inherited for power and mitigation, with contract owner source/target respectively. Other/custom graph call scopes remain unverified.';return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--journal',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-events',type=int);a=p.parse_args();assert not a.output.exists();r=audit(a.journal,json.loads(a.pins.read_bytes())['rules'],a.max_events);r['journal']=str(a.journal);r['pins_sha']=hashlib.sha256(a.pins.read_bytes()).hexdigest();r['helper_sha']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'failures':r['failures'][:4],'graph_checked':r['graph_context_calls_checked'],'identity_counts':r['identity_counts']}));raise SystemExit(0 if r['source_formula_consistent'] else 1)
if __name__=='__main__':main()
