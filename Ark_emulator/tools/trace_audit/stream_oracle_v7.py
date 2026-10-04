"""Journal-bound delta witnesses and ledger continuity; old audits preserved."""
import json
from pathlib import Path
from tools.trace_audit.stream_oracle_v5 import audit as audit_v5
from tools.trace_audit.stream_oracle_v6 import delta_audit
from tools.trace_audit.stream_oracle_v5_math import oracle,number
from tools.compare_campaign_trace import exact


def corrected_ledger(path,pins,delta,witness,max_events=None):
    from tools.trace_audit.stream_oracle_v5_identity import STANDARD
    definitions={r['id']:r for r in json.loads(STANDARD.read_bytes())['rules']}
    proved={e['event']:e for e in delta['verified']}
    prior={};bounds={};checks=[]
    with Path(path).open(encoding='utf8') as f:
        for count,line in enumerate(f,1):
            e=json.loads(line);v=e['payload'];t=v.get('trace',{})
            if e['type']=='calculation' and t.get('rule_id')=='rule/ark_resource_bounds':
                pin=pins.get(t['rule_id'])
                definition=definitions.get(t.get('rule_id'))
                if (pin and definition and t.get('rule_fingerprint')==pin['rule_fingerprint']
                    and exact(t.get('parameters'),definition.get('parameters',{}))
                    and t.get('runtime_fingerprint')==witness['rule_runtime_fingerprint']):
                    want=oracle(t['rule_id'],t['inputs'],t['parameters'])
                    if exact(want,t['value']) and exact(want,t['raw']):
                        c=t['context'];bounds[(c.get('owner_id'),c.get('resource'))]=want
            elif e['type']=='resource.changed':
                key=(v['target'],v['resource'])
                if 'value' not in v:
                    proof=proved.get(e['id'])
                    if proof is not None:
                        prior[key]=proof['after']
                    else:prior.pop(key,None)
                    bounds.pop(key,None)
                else:
                    value=number(v['value']);change=number(v['delta']);old=prior.get(key);bound=bounds.pop(key,None)
                    if old is not None and bound is not None:
                        checks.append({'event':e['id'],'target':key[0],'resource':key[1],'before':old,'after':value,'delta':change,
                            'bounded_value':bound['value'],'passed':exact(bound['value'],value) and exact(value-old,change)})
                    prior[key]=value
            if max_events and count>=max_events:break
    return checks


def audit(path,pins,witness,max_events=None):
    result=audit_v5(path,pins,max_events)
    delta=delta_audit(path,pins,witness,max_events)
    shape_ids=set(delta['handled']);verified_ids={r['event'] for r in delta['verified']}
    ledger=corrected_ledger(path,pins,delta,witness,max_events)
    corrections={r['event']:r for r in ledger if r['passed']}
    superseded=[];remaining=[]
    for failure in result['failures']:
        ident=failure.get('event')
        if ident in verified_ids and failure.get('field')=='resource.changed' and failure.get('reason')=="'value'":
            superseded.append({'old_failure':failure,'new_proof':'strict before/body/bounds/after verified delta-only event'})
        elif ident in corrections and failure.get('field')=='resource.delta':
            superseded.append({'old_failure':failure,'new_proof':corrections[ident]})
        else:remaining.append(failure)
    failures=remaining+delta['failures']+[{'event':r['event'],'field':'resource.ledger_v7','reason':'Strict corrected ledger mismatch','proof':r} for r in ledger if not r['passed']]
    result.update(schema='ark-sim/source-formula-stream-audit/v7',failures=failures,source_formula_consistent=not failures,
        all_fields_independently_verified=not failures and not result['pending_fields'],delta_only_resource_v7=delta,
        corrected_resource_ledger={'verified':sum(r['passed'] for r in ledger),'failed':[r for r in ledger if not r['passed']]},
        superseded_verifier_failures=superseded,
        delta_scope='Caller-bound runtime plus exact standard rule/source before resource, independently calculated bounds, unchanged source/target identity, actual post-resource witness. No event.value synthesized; previous ledger advances only after fully verified delta-only packet.',
        client_verified=False)
    result['counts']['failed']=len(failures)
    return result
