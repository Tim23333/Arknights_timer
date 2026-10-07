"""V5 formulas unchanged; source-bound delta-only resource shape is separately reviewed.

Never synthesize event.value. Bounds arithmetic is independently calculated;
pre/post actor resources are captured input witnesses, not a lifecycle oracle.
"""
import hashlib,json
from collections import Counter
from pathlib import Path
from tools.trace_audit.stream_oracle_v5 import audit as audit_v5
from tools.trace_audit.stream_oracle_v5_identity import STANDARD
from tools.trace_audit.stream_oracle_v5_math import number,oracle,Pending,finite_tree
from tools.compare_campaign_trace import exact,integer
ROOT=Path(__file__).resolve().parents[2]
def equal(a,b,msg):
 if not exact(a,b):raise ValueError(msg)
def delta_audit(path,pins,witness,max_events=None):
 defs={d['id']:d for d in json.loads(STANDARD.read_bytes())['rules']};prior={};bodies={};bounds={};waiting={};failures=[];pending=Counter();handled=[];verified=[];events=0
 def fail(e,msg):failures.append({'event':e['id'],'time':e['time'],'field':'resource.delta_only','reason':msg})
 def context(e,t):
  equal(t['contract_version'],1,'contract version');equal(t['numeric'],{'backend':'float','rounding':'half_even'},'numeric profile');c=t['context'];equal(c['time'],e['time'],'context time');equal(c['seconds'],e['time']*(1/30),'context seconds');equal(c['quantum'],1/30,'context quantum');integer(c['time'],'context time');return c
 def known(e,t):
  p=pins.get(t.get('rule_id'));d=defs.get(t.get('rule_id'))
  if not p or not d or t.get('rule_fingerprint')!=p['rule_fingerprint']:raise Pending('delta_only.bound_rule not source-reviewed')
  c=context(e,t);equal(t['calculation_id'],p['contract'],'calculation contract');equal(t['parameters'],d.get('parameters',{}),'source parameters');equal(e['payload']['calculation_id'],t['calculation_id'],'payload calculation identity');equal(e['payload']['rule_id'],t['rule_id'],'payload rule identity')
  if p.get('provider') is not None:equal(t.get('provider'),p['provider'],'provider source identity')
  want=oracle(t['rule_id'],t['inputs'],t['parameters']);equal(t['raw'],want,'raw independent arithmetic');equal(t['value'],want,'value independent arithmetic');equal(e['payload']['value'],want,'payload independent arithmetic')
  return c,want
 with Path(path).open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);events+=1;v=e.get('payload',{});k=e.get('type');t=v.get('trace',{});rid=t.get('rule_id')
   try:
    if k=='calculation' and rid=='rule/ark_damage_pipeline':
     actor=t.get('inputs',{}).get('target',{});owner=actor.get('id')
     for resource,row in actor.get('components',{}).get('resources',{}).items():bodies[(owner,resource)]={'event':e,'trace':t,'current':row.get('current'),'spec':row.get('spec',{})}
    elif k=='calculation' and t.get('calculation_id')=='resource.bounds':
     c=t.get('context',{});bounds[(c.get('owner_id'),c.get('resource'))]={'event':e,'trace':t}
    elif k=='resource.changed':
     key=(v['target'],v['resource'])
     if 'value' in v:prior[key]={'event':e['id'],'value':number(v['value'])};continue
     handled.append(e['id']);integer(v['target'],'changed target');assert type(v['resource']) is str and v['resource'];delta=number(v['delta']);bound=bounds.pop(key,None);body=bodies.get(key);old=prior.get(key)
     if not bound or not body or not old:raise Pending('delta_only.before or known bounds witness missing')
     bc,want=known(bound['event'],bound['trace']);pc,_=known(body['event'],body['trace']);actor=body['trace']['inputs']['target'];owner=integer(bc['owner_id'],'bounds owner');equal(owner,v['target'],'bounds owner must actual changed target');equal(owner,bc['target_id'],'bounds target identity');equal(bound['event']['payload']['target'],owner,'bounds payload target');equal(bound['event']['payload']['source'],bc['source_id'],'bounds payload source');equal(actor['id'],owner,'actual before body target');equal(pc['target_id'],owner,'before context target');equal(body['event']['payload']['target'],owner,'before payload target');equal(body['trace']['inputs']['source']['id'],pc['source_id'],'before source body/context');equal(body['event']['payload']['source'],pc['source_id'],'before payload source');equal(bound['trace']['runtime_fingerprint'],body['trace']['runtime_fingerprint'],'witness runtime binding');equal(bound['trace']['runtime_fingerprint'],witness['rule_runtime_fingerprint'],'reviewed delta scope runtime');equal(bound['event']['time'],e['time'],'bounds current time');equal(body['event']['time'],e['time'],'before body current time');equal(bc['source_id'],v.get('source'),'delta/source must match bounds source');equal(pc['source_id'],v.get('source'),'delta/source must match actual before source');equal(number(body['current']),old['value'],'body before differs from previous actual resource value');equal(old['value']+delta,number(bound['trace']['inputs']['candidate']),'before+delta differs from bounds candidate')
     spec=body['spec']
     if 'capacity' not in spec or 'capacity_attribute' in spec or 'capacity_rule' in spec:raise Pending('delta_only.dynamic capacity source oracle not reviewed')
     equal(number(bound['trace']['inputs']['capacity']),number(spec['capacity']),'bounds capacity differs from actual before resource spec');assert want['accepted'] is True;equal(want['value'],old['value']+delta,'delta-only expected bounds output');equal(bound['trace']['stages'][-1]['raw'],want,'bounds stage.raw');waiting[key]={'event':e,'before':old,'body':body,'bounds':bound,'after':want['value']}
    elif k=='calculation' and t.get('calculation_id')=='lifecycle.death':
     w=witness['post_input_witness']
     if not waiting:continue
     if rid!=w['rule_id'] or t.get('rule_fingerprint')!=w['rule_fingerprint']:raise Pending('delta_only.post input source identity unreviewed')
     c=context(e,t);equal(t['parameters'],w['parameters'],'post source parameters');equal(t['provider'],w['provider'],'post provider source identity');equal(t['calculation_id'],w['contract'],'post contract');equal(v['target'],c['target_id'],'post payload/target context');assert c['owner_id'] is None;assert c['source_id'] is None;equal(t['raw'],t['value'],'post raw/value identity consistency');equal(t['stages'][-1]['raw'],t['raw'],'post stage.raw consistency');equal(v['value'],t['value'],'post payload value consistency')
     for resource,row in t['inputs']['resources'].items():
      key=(c['target_id'],resource);item=waiting.get(key)
      if item is None:continue
      change=item['event'];equal(t['runtime_fingerprint'],item['bounds']['trace']['runtime_fingerprint'],'post witness runtime');equal(e['time'],change['time'],'post body current time');equal(t['inputs']['damage_event']['resource'],resource,'post damage-event resource');equal(t['inputs']['damage_event']['delta'],change['payload']['delta'],'post delta binding');equal(number(row['current']),item['after'],'post body current differs from independent bound output');equal(row.get('spec'),item['body']['spec'],'post resource spec differs from before');verified.append({'event':change['id'],'before_event':item['before']['event'],'before_body_event':item['body']['event']['id'],'bounds_event':item['bounds']['event']['id'],'after_body_event':e['id'],'target':c['target_id'],'resource':resource,'before':item['before']['value'],'delta':change['payload']['delta'],'after':item['after']});prior[key]={'event':change['id'],'value':item['after']};waiting.pop(key)
   except Pending as exc:pending[str(exc)]+=1
   except (ValueError,KeyError,AssertionError,TypeError) as exc:fail(e,str(exc))
   if max_events and events>=max_events:break
 for item in waiting.values():pending['delta_only.post same-owner/time body witness missing']+=1
 return {'handled':handled,'verified':verified,'failures':failures,'pending_fields':dict(pending),'event_count':events}
def audit(path,pins,max_events=None):
 result=audit_v5(path,pins,max_events);w=json.loads((ROOT/'validation/trace_audit/delta_only_v6/input_witness_pins.json').read_bytes());extra=delta_audit(path,pins,w,max_events);ids=set(extra['handled']);shape=[f for f in result['failures'] if f.get('event') in ids and f.get('field')=='resource.changed' and f.get('reason')=="'value'"];result['failures']=[f for f in result['failures'] if f not in shape]+extra['failures'];result['counts']['failed']=result['counts'].get('failed',0)-len(shape)+len(extra['failures']);result['delta_only_resource_v6']=extra;combined=Counter(result['pending_fields']);combined.update(extra['pending_fields']);result['pending_fields']=dict(combined);result['schema']='ark-sim/source-formula-stream-audit/v6';result['source_formula_consistent']=not result['failures'];result['all_fields_independently_verified']=not result['failures'] and not result['pending_fields'];result['delta_only_scope']='Known standard bounds identity/input/raw/value + same-time source/target/resource actual before body/prior change and post lifecycle input resource/current. Lifecycle algorithm remains unverified; no event.value fabricated.';return result
