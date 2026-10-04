"""Executable interface prototype, not an ArkSim consumer or game proof."""
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'packages/campaign/chapter09_source_prepare'

def number(value, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError('finite numeric parameter required')
    return value

def new_state(capacity, elements):
    number(capacity, minimum=1)
    if not elements or any(type(e) is not int or e < 1 for e in elements) or len(set(elements)) != len(elements):
        raise ValueError('finite unique element IDs required')
    return {'capacity':capacity,'remaining':{e:capacity for e in elements},'break':None,'generation':0}

def apply_loss(state, element, raw, resistance, neutral, now, duration, cause):
    # Validate the complete request before returning a plan or updated state.
    number(raw); number(resistance); number(now); number(duration, minimum=0.000001)
    if resistance > 100 or type(neutral) is not bool or type(element) is not int or element not in state['remaining']:
        raise ValueError('invalid element request')
    if neutral or state['break'] is not None or raw == 0:
        return state, ()
    updated = copy.deepcopy(state)
    updated['remaining'][element] = max(0, state['remaining'][element] - raw*(1-resistance*.01))
    if updated['remaining'][element] == 0:
        updated['generation'] += 1
        updated['break'] = {'element':element,'until':now+duration,'generation':updated['generation'],'cause':cause}
        return updated, ({'op':'break.start','element':element,'cause':cause},)
    return updated, ()

def recover(state, rate, dt, now):
    number(rate); number(dt); number(now)
    if state['break'] is not None:
        if now < state['break']['until']:
            return state
        updated = copy.deepcopy(state)
        updated['remaining'] = {key:state['capacity'] for key in state['remaining']}
        updated['break'] = None
        return updated
    if rate == 0 or dt == 0:
        return state
    updated = copy.deepcopy(state)
    updated['remaining'] = {key:min(state['capacity'], val+rate*dt) for key,val in state['remaining'].items()}
    return updated

def register(level, bucket, records):
    return {(level,bucket,i):copy.deepcopy(row) for i,row in enumerate(records)}

def resolve_alias(registry, alias):
    found = [key for key,row in registry.items() if row['alias']==alias]
    if len(found) != 1:
        raise ValueError('ambiguous or missing native alias; exact record identity required')
    return found[0]

def collapse_cells(origin, attacker):
    # Explicit prototype geometry policy: cardinal adjacency only, opposite source.
    dx,dy=attacker[0]-origin[0],attacker[1]-origin[1]
    if abs(dx)+abs(dy)!=1:
        raise ValueError('cardinal adjacent source required')
    return tuple((origin[0]-dx*i, origin[1]-dy*i) for i in (1,2))

def main():
    policy_path=BASE/'elemental.policy.source.v1.json'
    policy=json.loads(policy_path.read_bytes())
    defaults=policy['reference']['defaults']; duration=policy['native']['fire']['elementBreakDuration']
    tests=[]
    def check(name, condition):
        assert condition, name
        tests.append({'name':name,'passed':True})
    s=new_state(defaults['capacity'],[1,3]); original=copy.deepcopy(s)
    a,plan=apply_loss(s,3,999,0,False,1,duration,'source-A')
    check('near threshold no break',a['remaining'][3]==1 and not plan and s==original)
    b,plan=apply_loss(a,3,1,0,False,2,duration,'source-B')
    check('threshold owns exact triggering cause',b['break']=={'element':3,'until':12,'generation':1,'cause':'source-B'} and len(plan)==1)
    check('global break loss locked',apply_loss(b,1,5000,0,False,3,duration,'source-C')[0] is b)
    check('global break recovery locked',recover(b,100,2,11) is b)
    c=recover(b,0,1,12)
    check('expiry resets every resource',c['remaining']=={1:1000,3:1000} and c['break'] is None)
    check('50percent resistance',apply_loss(s,3,100,50,False,0,duration,None)[0]['remaining'][3]==950)
    check('neutral request no state write',apply_loss(s,3,100,0,True,0,duration,None)[0] is s)
    check('zero loss no state write',apply_loss(s,3,0,0,False,0,duration,None)[0] is s)
    check('source configurable boss threshold',apply_loss(new_state(defaults['boss_capacity'],[3]),3,1000,0,False,0,duration,None)[0]['remaining'][3]==1000)
    check('non-hardcoded capacity',apply_loss(new_state(753,[3]),3,753,0,False,0,duration,None)[0]['break'] is not None)
    check('recovery finite clamp',recover(a,100,20,2)['remaining'][3]==1000)
    for label,args in [('bool damage',(True,0,False)),('nan damage',(math.nan,0,False)),('infinite resistance',(1,math.inf,False)),('bool neutral',(1,0,1)),('resistance over100',(1,101,False))]:
        try:apply_loss(s,3,*args,0,duration,None)
        except ValueError:check(label+' rejected atomically',s==original)
        else:raise AssertionError(label)
    rows=[{'alias':'trap_043_dupilr#1','position':p} for p in [(5,4),(2,7),(3,4)]]
    reg=register('main_09-16','tokenInst',rows)
    check('duplicate raw aliases preserved with distinct record IDs',len(reg)==3 and list(reg.values())==rows)
    try:resolve_alias(reg,'trap_043_dupilr#1')
    except ValueError:check('ambiguous raw alias rejects',True)
    else:raise AssertionError('ambiguous alias')
    check('source opposite two-cell collapse geometry',collapse_cells((4,4),(5,4))==((3,4),(2,4)))
    check('four cardinal directions remain distinct',len({collapse_cells((4,4),p) for p in [(5,4),(3,4),(4,5),(4,3)]})==4)
    result={'schema':'ark-sim/c9-parameter-prototype-report/v1','scope':'Pure source-parameter contract prototype; no ArkSim runtime, events, CP/head or client validation.',
            'source':{'path':str(policy_path),'sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest()},
            'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'tests':tests,'test_count':len(tests),'all_passed':True}
    out=Path('E:/ArkSimLogs/runs/chapter09_parameter_prototype_v1');out.mkdir(parents=True,exist_ok=True)
    report=out/'report.json';assert not report.exists();report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    receipt=BASE/'parameter.prototype.receipt.v1.json';assert not receipt.exists()
    receipt.write_text(json.dumps({'report':str(report),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),**result},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tests':len(tests),'report':str(report),'receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()}))

if __name__=='__main__':
    main()
