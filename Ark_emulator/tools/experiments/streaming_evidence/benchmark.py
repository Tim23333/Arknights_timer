"""Same complete event value hash, lower bounded export allocation."""
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
import tracemalloc

ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.contracts import freeze,digest
from tools.campaign_streaming_evidence import canonical_hash


def main():
    # One immutable nested payload is intentionally reused; the old serializer
    # expands its full JSON value per event, as it must for canonical evidence.
    payload=freeze({'calculation_id':'probe','inputs':{'source':{'hp':100,'buffs':list(range(200))}},'result':80})
    events=freeze([{'id':i+1,'type':'calculation','payload':payload,'time':i,'cause':None} for i in range(5000)])
    rows=[]
    for name,operation in [('whole_tree',digest),('stream',canonical_hash)]:
        gc.collect();tracemalloc.start();start=time.perf_counter();value=operation(events);elapsed=time.perf_counter()-start
        current,peak=tracemalloc.get_traced_memory();tracemalloc.stop();rows.append({'method':name,'sha256':value,'elapsed_seconds':elapsed,'peak_incremental_bytes':peak})
    assert rows[0]['sha256']==rows[1]['sha256'] and rows[1]['peak_incremental_bytes']<rows[0]['peak_incremental_bytes']/4
    report={'schema':'ark-sim/canonical-export-allocation-benchmark/v1','passed':True,'events':len(events),'results':rows,
        'all_event_values_preserved':True,'scope':'synthetic immutable nested journal serialization, not fullstage RSS/core-storage proof',
        'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'tools/campaign_streaming_evidence.py']}}
    out=ROOT/'validation/campaign/streaming_evidence/serialization_allocation.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(rows))


if __name__=='__main__':main()
