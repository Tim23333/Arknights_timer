"""Capture SourceCombat2 after actual blocking reconciliation."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'packages/campaign/chapter05_units/special/model.ranged_guard.reference.json'
PIN='a491491f577f5842660ddbcff3a6eda0cfab1fff9f4994c1cb04f107bc6463dc'
OUT=ROOT/'packages/campaign/chapter05_units/special/model.selection_settle.reference.json'
def build():
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest()==PIN;p=json.loads(PARENT.read_bytes())
    ability=next(a for a in p['abilities'] if a['id']=='ability/ch5/special/enemy_1038_lunmag/normal')
    ability['activation']['settle_blocking']=True
    p['manifest']['id']+='/selection_settle';p['manifest']['metadata'].update(parent_sha=PIN,
        selection_settle_builder_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        selection_settle_policy='SourceCombat2 capture reconciles actual blocker before target query; no stale first-frame fallback or slot duplication',
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
