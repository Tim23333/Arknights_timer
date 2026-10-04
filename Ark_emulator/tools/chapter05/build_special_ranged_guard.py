"""Correct source ranged trigger behavior; preserve combat INPUT_TARGET2 gate."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'packages/campaign/chapter05_units/special/model.reference.json'
PIN='cbc8ad5806e5ae7801e9d58e7d92542ab45567b42675a82a47c8b7cad4195579'
OUT=ROOT/'packages/campaign/chapter05_units/special/model.ranged_guard.reference.json'
def build():
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PIN
    p=json.loads(PARENT.read_bytes());behavior=next(b for b in p['behaviors'] if b['id']=='behavior/ch5/special/enemy_1038_lunmag')
    params=behavior['decision']['profiles'][0]['parameters'];assert params['blocked_target'] is True
    params['blocked_target']=False
    p['manifest']['id']+='/ranged_guard'
    p['manifest']['metadata'].update(parent_sha=PIN,ranged_guard_builder_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        ranged_trigger_policy='Actual ranged SelectorTrigger allows unblocked target; combat INPUT_TARGET2 still hard current blocker when blocked, no duplicate shared-PPtr attack',
        independent_reviewed=False)
    p['manifest']['metadata']['source_locks'][str(PARENT.relative_to(ROOT))]=PIN
    return p
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:assert OUT.read_bytes()==raw
    else:
        with OUT.open('xb') as f:f.write(raw)
    print(json.dumps({'sha':hashlib.sha256(raw).hexdigest(),'full_stage_executed':False}))
if __name__=='__main__':main()
