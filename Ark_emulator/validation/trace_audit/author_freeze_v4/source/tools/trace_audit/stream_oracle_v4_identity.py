"""Strict trace identity plus independently calculated arithmetic; v1 stays frozen."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.trace_audit import stream_oracle_v4_math as base
from tools.compare_campaign_trace import exact,integer
STANDARD=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate/ark_sim/content/presets/ark_standard.json'
STANDARD_SHA='1070ba6793cee5ded71c0f0b89a96ba72973d49989407e70a858a575febb9814'
def audit(path,pins,max_events=None):
 assert hashlib.sha256(STANDARD.read_bytes()).hexdigest()==STANDARD_SHA
 definitions={r['id']:r for r in json.loads(STANDARD.read_bytes())['rules']};result=base.audit(path,pins,max_events);failures=[];pending=Counter();counts=Counter();sources={}
 def fail(e,field,reason,want=None,actual=None):
  counts['identity_or_arithmetic_failures']+=1
  if len(failures)<50:failures.append({'event':e.get('id'),'time':e.get('time'),'field':field,'reason':reason,'expected':want,'actual':actual})
 def trace(e,t,node=None,nested=False):
  prefix='nested.' if nested else 'trace.';rid=t.get('rule_id');pin=pins.get(rid);definition=definitions.get(rid)
  if not pin or not definition:pending[prefix+str(rid)+': source formula/definition not reviewed']+=1;return False
  if t.get('rule_fingerprint')!=pin['rule_fingerprint']:pending[prefix+rid+': source rule fingerprint not reviewed']+=1;return False
  valid=True
  def require(field,want,actual):
   nonlocal valid
   if not exact(want,actual):valid=False;fail(e,prefix+field,'trace identity/value differs from source-bound expectation',want,actual)
  require('calculation_id',pin['contract'],t.get('calculation_id'));require('calculation_id.source_definition',definition['contract'],t.get('calculation_id'));require('contract_version',1,t.get('contract_version'));require('numeric',{'backend':'float','rounding':'half_even'},t.get('numeric'))
  require('parameters',definition.get('parameters',{}),t.get('parameters'))
  ctx=t.get('context',{});require('context.time',e.get('time'),ctx.get('time'));require('context.quantum',1/30,ctx.get('quantum'));require('context.seconds',e.get('time',0)*(1/30),ctx.get('seconds'))
  try:integer(ctx['time'],'trace context tick');base.number(ctx['quantum']);base.number(ctx['seconds'])
  except (KeyError,ValueError) as exc:valid=False;fail(e,prefix+'context',str(exc))
  if pin.get('provider') is not None:require('provider',pin['provider'],t.get('provider'))
  elif 'provider' in t:valid=False;fail(e,prefix+'provider','unexpected provider for source expression/graph')
  implementation=definition['implementation']
  if implementation['type']=='expression':
   require('expression',implementation['expression'],t.get('stages',[{}])[-1].get('expression'))
  elif implementation['type']=='provider':
   require('provider.name',implementation['provider'],t.get('provider',{}).get('name'))
  elif implementation['type']=='graph':
   require('graph.node_order',[n['id'] for n in implementation['nodes']],[n.get('id') for n in t.get('stages',[])])
   for spec,node_record in zip(implementation['nodes'],t.get('stages',[])):
    if 'expression' in spec:require('graph.'+spec['id']+'.expression',spec['expression'],node_record.get('trace',{}).get('expression'))
  if valid:
   try:
    want=base.oracle(rid,t['inputs'],t['parameters'])
    require('raw',want,t.get('raw'));require('value',want,t.get('value'));require('stage.final.raw',want,t.get('stages',[{}])[-1].get('raw'))
    if node is not None:
     if node.get('kind')=='calculation':
      require('callback.fields',['calculation_id','id','kind','rule_id','trace','value'],sorted(node))
      require('callback.id','calculation:'+t['calculation_id'],node.get('id'));require('callback.calculation_id',t['calculation_id'],node.get('calculation_id'));require('callback.rule_id',rid,node.get('rule_id'));require('callback.value',want,node.get('value'))
     elif 'kind' not in node:
      require('graph.fields',['id','raw','trace','value'],sorted(node));require('node.raw',want,node.get('raw'));require('node.value',want,node.get('value'))
     else:pending[prefix+'wrapper kind not source-reviewed']+=1;valid=False
   except base.Pending as exc:pending[prefix+str(exc)]+=1;valid=False
   except (KeyError,ValueError,AssertionError,TypeError) as exc:valid=False;fail(e,prefix+'formula',str(exc))
  for childnode in t.get('stages',[]):
   child=childnode.get('trace',{})
   if 'rule_id' in child and not trace(e,child,childnode,True):valid=False
  if valid:counts['identity_verified_nested' if nested else 'identity_verified_calculations']+=1
  return valid
 with Path(path).open(encoding='utf8') as f:
  for line in f:
   try:e=json.loads(line);base.finite_tree(e);integer(e['id'],'event ID');integer(e['time'],'event tick')
   except (ValueError,KeyError) as exc:fail(locals().get('e',{}),'encoding',str(exc));continue
   counts['identity_events']+=1;v=e['payload'];kind=e['type']
   if kind=='calculation':
    t=v.get('trace',{});valid=trace(e,t)
    if not exact(v.get('calculation_id'),t.get('calculation_id')) or not exact(v.get('rule_id'),t.get('rule_id')):fail(e,'payload.calculation_identity','payload/trace identities differ');valid=False
    ctx=t.get('context',{});owner=ctx.get('owner_id') or ctx.get('source_id') or ctx.get('target_id');sources[e['id']]={'valid':valid,'value':v.get('value'),'calculation_id':t.get('calculation_id'),'owner':owner,'attribute':ctx.get('attribute'),'time':e['time']}
   elif kind=='calculation.cached':
    try:
     ref=integer(v['source_event_id'],'cached source ID');owner=integer(v['owner'],'cached owner');integer(e['cause'],'cached cause');source=sources.get(ref)
     if source is None or not source['valid']:pending['cached.source: absent or independently unverified identity/formula']+=1;continue
     checks={'source_event_id.backward':ref<e['id'],'cause_binding':exact(e['cause'],ref),'calculation_id':exact(source['calculation_id'],v.get('calculation_id')),'owner':exact(source['owner'],owner),'attribute':exact(source['attribute'],v.get('attribute')),'value':exact(source['value'],v.get('value'))}
     invalid=[k for k,ok in checks.items() if not ok]
     if invalid:fail(e,'cached.identity','verified source differs in '+','.join(invalid))
     else:counts['identity_verified_cached']+=1
    except (KeyError,ValueError) as exc:fail(e,'cached.identity',str(exc))
   if max_events and counts['identity_events']>=max_events:break
 result['schema']='ark-sim/source-formula-stream-audit/v2';result['source_standard_definition_sha']=STANDARD_SHA;result['identity_counts']=dict(counts);result['failures']+=failures;combined=Counter(result['pending_fields']);combined.update(pending);result['pending_fields']=dict(combined);result['source_formula_consistent']=not result['failures'];result['all_fields_independently_verified']=not result['failures'] and not result['pending_fields'];result['counts']['verified_calculations']=counts['identity_verified_calculations'];result['counts']['verified_nested_calculations']=counts['identity_verified_nested'];result['counts']['verified_cached']=counts['identity_verified_cached'];result['scope']='Source arithmetic plus explicit rule/params/numeric/contract/context/cache identity. Source birth/maxHP and unsupported rules remain pending; no client accuracy approval.';return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--journal',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-events',type=int);a=p.parse_args();assert not a.output.exists();r=audit(a.journal,json.loads(a.pins.read_bytes())['rules'],a.max_events);r['journal']=str(a.journal);r['pin_sha']=hashlib.sha256(a.pins.read_bytes()).hexdigest();r['helper_sha']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'failures':r['failures'][:4],'identity_counts':r['identity_counts'],'pending':r['pending_fields']}));raise SystemExit(0 if r['source_formula_consistent'] else 1)
if __name__=='__main__':main()
