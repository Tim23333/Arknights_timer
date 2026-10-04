"""Read-only exact 4-10 source inventory; does not author or change Ice modules."""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    path=ROOT/'packages/campaign/chapter04_plans/source.plan.json';plan=json.loads(path.read_bytes());stage=plan['stages']['level_main_04-10'];native=stage['native_document'];mp=native.get('map',native.get('mapData',{}));print(json.dumps({'plan_sha':sha(path),'stage_keys':list(stage),'native_keys':list(native),'map_keys':list(mp),'births':stage['spawn_count'],'variants':stage['variant_ids'],'options':native.get('options'),'tiles':dict(Counter(t['tileKey'] for t in mp.get('tiles',[]))),'teleport_routes':[(i,r) for i,r in enumerate(native.get('routes') or []) if any('TELEPORT' in str(c) for c in (r.get('checkpoints') or []))]},ensure_ascii=False))
    print(json.dumps({'stage_extra':{k:v for k,v in stage.items() if k not in ('native_document','variant_ids')},'variant_bindings':{vid:plan['variants'][vid].get('native_reference') for vid in stage['variant_ids']}},ensure_ascii=False))
if __name__=='__main__':main()
