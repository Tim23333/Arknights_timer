"""Freeze byte-preserving bounded primitive delta, not promotion authorization."""
import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c9_depletion_v2_candidate').resolve()
PARENT=(ROOT/'../unpack_work/campaign_c9_foundation_v9_candidate').resolve()
sys.path.insert(0,str(CAND))
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter09_depletion'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=implementation_digest();delta=[]
for p in sorted((CAND/'ark_sim').rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
    rel=p.relative_to(CAND);old=PARENT/rel
    if not old.exists() or p.read_bytes()!=old.read_bytes():
        target=ROOT/'tools/chapter09_depletion/source_delta.v2'/rel
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        delta.append({'path':rel.as_posix(),'parent_sha256':sha(old) if old.exists() else None,'candidate_sha256':sha(p),'saved_delta_sha256':sha(target)})
reports=[]
for name in ['author.primitive.v2.json','author.strict.v2.json','author.context.v2.json']:
    p=OUT/name;r=json.loads(p.read_bytes())
    assert r['actual_exit']==0 and r['core_before']==r['core_after']==before
    assert all(x['passed'] for x in r['results'])
    reports.append({'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p),'actual_exit':r['actual_exit'],'groups':len(r['results']),'core_before':r['core_before'],'core_after':r['core_after']})
helpers=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in sorted((ROOT/'tools/chapter09_depletion').glob('*.py'))]
assert before==implementation_digest()
report={'schema':'ark-sim/compact-freeze-receipt/v1','candidate':str(CAND),'parent':str(PARENT),'parent_core':'56f380fab9715b8edcb589b2c3fc3863d740cb149ab31e19b3f6fe3a1720fcf6','core_before':before,'core_after':implementation_digest(),'actual_author_groups':12,'reports':reports,'delta':delta,'helpers':helpers,'scope':'Bounded exact-zero defer/ready finite callbacks; author evidence only, requires independent review before merge/promotion','historical_failures_preserved':['parent.counter.v1.json','root_due_tamper.counter.json','development.lineage_failure.d063.json','author.primitive.frozen.a218.json','development.context.fixture_failure.v2.json'],'pending':['source-owned tile-target cast bridge and full native pillar direction/collapse payload','source duspfr three-second five-parallel payload','full-suite/baseline and independent restore review'],'trust_boundary':'Validates declared rules and pure traces against frozen source, original clock, finite slots, queue and causal event ledger. Not a cryptographic signature authenticating arbitrary replacement of every checkpoint field.'}
(OUT/'freeze.v2.final.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({'core':before,'files':len(delta),'groups':12,'freeze_sha256':sha(OUT/'freeze.v2.final.json')}))
