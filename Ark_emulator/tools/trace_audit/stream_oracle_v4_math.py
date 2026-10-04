"""Offline source-formula oracle. No ark_sim calculator/runtime imports."""
import argparse,hashlib,json,math,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.compare_campaign_trace import exact,integer
class Pending(Exception):pass
def number(v):
 if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('finite numeric field required; bool rejected')
 return v
def finite_tree(v):
 if type(v) in (int,float):number(v)
 elif isinstance(v,dict):
  for item in v.values():finite_tree(item)
 elif isinstance(v,list):
  for item in v:finite_tree(item)
def oracle(rule,inputs,params):
 n=number
 if rule=='rule/ark_damage_pipeline':
  e=inputs['effect'];power=oracle('rule/ark_basic_power',{'attack':e['attack'],'scale':e['scale'],'additions':e['additions']},{})
  amount=oracle('rule/ark_standard_mitigation',{'power':power,'defense':e['defense'],'resistance':e['resistance'],'damage_type':e['damage_type']},{'minimum_ratio':.05})
  return {'accepted':True,'amount':amount,'allocations':[],'events':[]}
 if rule in ('rule/ark_basic_power','rule/ark_healing_power'):return n(inputs['attack'])*n(inputs['scale'])+n(inputs['additions'])
 if rule=='rule/ark_standard_mitigation':
  power=n(inputs['power']);kind=inputs['damage_type'];assert n(params['minimum_ratio'])==.05
  if kind=='true':return power
  if kind=='physical':return max(power-n(inputs['defense']),power*.05)
  if kind=='arts':return max(power*(1-min(max(n(inputs['resistance']),0),100)/100),power*.05)
  raise Pending('unknown damage_type')
 if rule=='rule/ark_resource_capacity':return n(inputs['capacity_parameters']['capacity'])
 if rule=='rule/ark_resource_cost':return n(inputs['cost_parameters']['amount'])
 if rule=='rule/ark_resource_recovery':return n(inputs['current'])+n(inputs['parameters']['rate'])*n(inputs['delta_seconds'])
 if rule=='rule/ark_resource_bounds':
  v=n(inputs['candidate']);cap=n(inputs['capacity']);opts={**params,**inputs['bounds_parameters']};lo=n(opts.get('minimum',0));hi=n(opts.get('maximum',cap));mode=opts.get('mode','clamp')
  if mode not in ('reject','clamp'):raise Pending('unknown bounds mode')
  if mode=='reject' and not lo<=v<=hi:return {'value':v,'overflow':0,'accepted':False}
  bounded=min(hi,max(lo,v));return {'value':bounded,'overflow':v-bounded,'accepted':True}
 if rule=='rule/ark_modifier_layer':
  p=inputs['layer_parameters'];return (n(inputs['value'])+n(p['additive']))*(1+n(p['ratio']))*n(p['factor'])
 if rule=='rule/ark_attribute_layers':
  if params.get('aggregator',{}).get('provider')!='ark.attributes.aggregate':raise Pending('custom aggregator')
  val=n(inputs['base']);known={'flat':'add','direct_ratio':'ratio_sum','final_ratio':'ratio_product','final_add':'add','final_mul':'factor_product'}
  for row in inputs['order']:
   layer=row['layer'];mods=[m for m in inputs['modifier_layers'] if m.get('layer','flat')==layer]
   if not mods:continue
   op=params['operations'].get(layer);assert known.get(layer)==op
   if any(m.get('parameters',{}).get('time_curve') for m in mods):raise Pending('temporal modifier requires independently bound buff clock')
   values=[n(m['value'])*n(m.get('stacks',1)) for m in mods]
   if op=='add':val=(val+sum(values))*1*1
   elif op=='ratio_sum':val=(val+0)*(1+sum(values))*1
   elif op=='ratio_product':val=(val+0)*1*math.prod(1+v for v in values)
   elif op=='factor_product':val=(val+0)*1*math.prod(values)
  return val
 if rule=='rule/ark_deploy_cost':return n(inputs['base_cost'])*min(2,1+n(params['repeat_ratio'])*n(inputs['deployment_history']['count']))
 if rule=='rule/ark_deploy_refund':
  p=inputs['refund_parameters'];v=n(inputs['paid_cost'])*n(p['ratio']);return min(v,n(p['raw_cost'])*n(p['raw_cap_ratio'])) if 'raw_cap_ratio' in p else v
 raise Pending('rule has no independently defined oracle')
def audit(path,pins,max_events=None):
 counts=Counter();pending=Counter();failures=[];calc={};resources={};bounds={};resourcechecks=0;lastid=0
 def failed(e,field,reason,expected=None,actual=None):
  counts['failed']+=1
  if len(failures)<50:failures.append({'event':e.get('id'),'time':e.get('time'),'field':field,'reason':reason,'expected':expected,'actual':actual})
 with Path(path).open(encoding='utf8') as f:
  for line in f:
   try:e=json.loads(line);finite_tree(e);eid=integer(e['id'],'event ID');integer(e['time'],'event tick');assert eid>lastid;lastid=eid
   except (ValueError,AssertionError,KeyError) as exc:failed(locals().get('e',{}),'event_encoding',str(exc));continue
   counts['events']+=1;k=e['type'];v=e['payload']
   if k=='calculation':
    try:
     t=v['trace'];rule=t['rule_id'];pin=pins.get(rule)
     if v.get('rule_id')!=rule or v.get('calculation_id')!=t['calculation_id']:raise ValueError('payload/trace calculation identity differs')
     if not pin:raise Pending(rule+': unsupported rule')
     if t['rule_fingerprint']!=pin['rule_fingerprint']:raise Pending(rule+': fingerprint differs from reviewed source rule')
     if t['numeric']!={'backend':'float','rounding':'half_even'}:raise Pending(rule+': unsupported numeric profile')
     if t['contract_version']!=1 or t['calculation_id']!=pin['contract']:raise ValueError('contract identity differs')
     expected=oracle(rule,t['inputs'],t['parameters']);prior_failures=counts['failed']
     for field,actual in [('trace.raw',t['raw']),('trace.value',t['value']),('payload.value',v['value'])]:
      if not exact(expected,actual):failed(e,field,'independent source-formula mismatch',expected,actual)
     stage=t['stages'][-1]
     if not exact(expected,stage['raw']):failed(e,'trace.stages.final.raw','independent stage mismatch',expected,stage['raw'])
     if pin.get('expression') is not None and stage.get('expression')!=pin['expression']:raise ValueError('source expression differs from reviewed formula pin')
     if pin.get('provider') and t.get('provider')!=pin['provider']:raise ValueError('source provider identity differs')
     def check_nested(parent):
      for node in parent.get('stages',[]):
       child=node.get('trace',{})
       if 'rule_id' not in child:continue
       rid=child['rule_id'];cp=pins.get(rid)
       if not cp or child.get('rule_fingerprint')!=cp['rule_fingerprint']:pending[rid+': nested unknown rule/pin']+=1;continue
       try:
        want=oracle(rid,child['inputs'],child['parameters'])
        fields=[('nested.raw',child['raw']),('nested.value',child['value'])]
        if node.get('kind')=='calculation':
         if node.get('id')!='calculation:'+child['calculation_id'] or node.get('calculation_id')!=child['calculation_id'] or node.get('rule_id')!=rid or set(node)!={'id','kind','calculation_id','rule_id','value','trace'}:raise Pending('nested.callback wrapper shape/identity not reviewed')
         fields.append(('callback.value',node['value']))
        elif 'kind' not in node and set(node)=={'id','raw','value','trace'}:
         fields.extend([('graph.node.raw',node['raw']),('graph.node.value',node['value'])])
        else:raise Pending('nested.wrapper typed shape not reviewed')
        for field,actual in fields:
         if not exact(want,actual):failed(e,field,'independent nested source-formula mismatch',want,actual)
        counts['verified_nested_calculations']+=1;check_nested(child)
       except Pending as exc:pending[str(exc)]+=1
     check_nested(t)
     if rule=='rule/ark_damage_pipeline':
      nodes={node['id']:node for node in t['stages']};effect=t['inputs']['effect'];power=oracle('rule/ark_basic_power',{'attack':effect['attack'],'scale':effect['scale'],'additions':effect['additions']},{})
      for field,want in [('attack',effect['attack']),('scale',effect['scale']),('additions',effect['additions'])]:
       actual=nodes['power']['trace']['inputs'][field]
       if not exact(want,actual):failed(e,'graph.power.inputs.'+field,'parent input binding mismatch',want,actual)
      for field,want in [('power',power),('defense',effect['defense']),('resistance',effect['resistance']),('damage_type',effect['damage_type'])]:
       actual=nodes['mitigation']['trace']['inputs'][field]
       if not exact(want,actual):failed(e,'graph.mitigation.inputs.'+field,'graph dependency/input binding mismatch',want,actual)
     verified=counts['failed']==prior_failures
     if verified:counts['verified_calculations']+=1
     calc[eid]=(v['value'],verified)
     if verified and rule=='rule/ark_resource_bounds':
      owner=t['context'].get('owner_id') or t['context'].get('source_id') or t['context'].get('target_id');bounds[(owner,t['context'].get('resource'))]=expected
    except Pending as exc:pending[str(exc)]+=1;calc[eid]=(v.get('value'),False)
    except (KeyError,ValueError,AssertionError,TypeError) as exc:failed(e,'calculation.trace',str(exc));calc[eid]=(v.get('value'),False)
   elif k=='calculation.cached':
    source=calc.get(v.get('source_event_id'))
    if source is None or not source[1]:pending['cached.source_event_id: absent or unverified independent source']+=1
    elif not exact(source[0],v['value']):failed(e,'cached.value','cached result differs from verified source',source[0],v['value'])
    else:counts['verified_cached']+=1
   elif k=='resource.changed':
    key=(v['target'],v['resource'])
    try:
     value=number(v['value']);delta=number(v['delta']);old=resources.get(key)
     bounded=bounds.pop(key,None)
     if bounded is not None:
      if not exact(bounded['value'],value):failed(e,'resource.value','independently calculated bounds output differs',bounded['value'],value)
      if old is not None:
       if not exact(value-old,delta):failed(e,'resource.delta','bounded value minus previous resource differs',value-old,delta)
       else:resourcechecks+=1
     elif old is None:pending['resource.before: initial state not yet independently bound']+=1
     elif not exact(old+delta,value):pending['resource.transition: missing bounds witness/output normalization']+=1
     else:resourcechecks+=1
     if value<0:failed(e,'resource.value','negative resource value',0,value)
     resources[key]=value
     if v['resource']=='hp':pending['resource.hp.maximum: source-bound effective maxHP not yet covered']+=1
    except (KeyError,ValueError) as exc:failed(e,'resource.changed',str(exc))
   elif k in ('entity.created','entity.registered'):pending['lifecycle.birth: source definition/initial HP binding not yet covered']+=1
   if max_events and counts['events']>=max_events:break
 return {'schema':'ark-sim/source-formula-stream-audit/v1','source_formula_consistent':counts['failed']==0,'all_fields_independently_verified':counts['failed']==0 and not pending,'counts':dict(counts),'verified_resource_transitions':resourcechecks,'pending_fields':dict(pending),'failures':failures,'final_observed_resources':[{'entity':e,'resource':r,'value':v} for (e,r),v in resources.items()],'accuracy_scope':'Independent arithmetic from captured source-rule inputs; no client accuracy approval. Birth/maxHP source-binding and custom-rule coverage remain pending unless separately evidenced.','client_verified':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--journal',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-events',type=int);a=p.parse_args();assert not a.output.exists();pins=json.loads(a.pins.read_bytes());r=audit(a.journal,pins['rules'],a.max_events);r['journal']=str(a.journal);r['oracle_pins_sha']=hashlib.sha256(a.pins.read_bytes()).hexdigest();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'counts':r['counts'],'pending':r['pending_fields'],'failures':r['failures'][:3]}));raise SystemExit(0 if r['source_formula_consistent'] else 1)
if __name__=='__main__':main()
