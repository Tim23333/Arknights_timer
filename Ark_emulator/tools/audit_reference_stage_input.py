"""Audit source locks and executable typed actor state, without approving fidelity."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def audit(path,root=ROOT):
    raw=Path(path).read_bytes();package=json.loads(raw);meta=package['manifest']['metadata'];locks=meta.get('source_locks',{})
    checked=[];failures=[]
    for name,expected in locks.items():
        source=Path(name)
        if not source.is_absolute():source=Path(root)/source
        if not source.exists():failures.append({'path':name,'reason':'missing_source'});continue
        actual=hashlib.sha256(source.read_bytes()).hexdigest();checked.append({'path':name,'expected':expected,'actual':actual})
        if actual!=expected:failures.append({'path':name,'reason':'source_drift'})
    definitions={d['id']:d for d in package.get('definitions',[])}
    typed=[]
    for definition in definitions.values():
        if definition['kind']!='entity' or not set(definition.get('tags',[]))&{'enemy','player'}:continue
        state=definition['components'].get('selection_state')
        if not state or type(state.get('motion')) is not int or state['motion'] not in (1,2,3):
            failures.append({'definition':definition['id'],'reason':'missing_typed_motion'})
        else:typed.append({'definition':definition['id'],'motion':state['motion']})
    return {'schema':'ark-sim/reference-input-audit/v1','passed':not failures,'package_sha256':hashlib.sha256(raw).hexdigest(),
        'source_locks_checked':checked,'typed_actor_states':typed,'failures':failures,
        'scope':'Source byte locks and required typed motion only; no full semantic or stage acceptance claim',
        'actual_client_verified':False}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    report=audit(args.package);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':report['passed'],'checked_sources':len(report['source_locks_checked']),'failures':report['failures']}))
    raise SystemExit(0 if report['passed'] else 1)
