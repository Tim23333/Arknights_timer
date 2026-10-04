import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c9_pillar_lifecycle_v2_candidate').resolve();PARENT=(ROOT/'../unpack_work/campaign_c9_pillar_lifecycle_v1_candidate').resolve();sys.path.insert(0,str(CAND))
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter09_pillar_lifecycle_v2';TOOLS=ROOT/'tools/chapter09_pillar_lifecycle_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=implementation_digest();reports=[]
for name in ['author.initial.json','author.regression.json','author.context.json','author.restore.json']:
    path=OUT/name;r=json.loads(path.read_bytes());assert r['actual_exit']==0 and r['core_before']==r['core_after']==before
    reports.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':sha(path),'groups':len(r['results']),'actual_exit':r['actual_exit'],'core_before':r['core_before'],'core_after':r['core_after']})
delta=[]
for p in sorted((CAND/'ark_sim').rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
    rel=p.relative_to(CAND);old=PARENT/rel
    if not old.exists() or p.read_bytes()!=old.read_bytes():
        target=TOOLS/'source_delta'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);delta.append({'path':rel.as_posix(),'parent_sha256':sha(old) if old.exists() else None,'candidate_sha256':sha(p),'saved_delta_sha256':sha(target)})
cleanups=[]
for name in ['author.initial.json','author.regression.json']:cleanups+=json.loads((OUT/name).read_bytes())['cleanup']
module=ROOT/'packages/campaign/chapter09_consumers/pillar_lifecycle_v1/module.v1.json'
assert before==implementation_digest()
receipt={'schema':'ark-sim/compact-freeze-receipt/v1','candidate':str(CAND),'parent':str(PARENT),'parent_core':'03771a43a288c565ea89232fca337860e586e69dd55d6cb10f4f4a082a48fd29','core_before':before,'core_after':implementation_digest(),'reports':reports,'actual_author_groups':sum(r['groups'] for r in reports),'delta':delta,'helpers':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in sorted(TOOLS.glob('*.py'))],'module':{'path':str(module.relative_to(ROOT)).replace('\\','/'),'sha256':sha(module),'content_unchanged_from_v1':True},'scope':'Fix missing finite lifecycle owner on restore: living HP0/exhausted generation requires valid lease; unstarted stage cannot borrow depleted state; declared plan original generation transition checked; no orphan pending action tasks; legal dead/withdrawn/finish states retained. Includes fresh pillar12, primitive10, customcontext2 and restore5 on final core.','root_counter':'validation/campaign/chapter09_depletion_root_peer/missing_lease.counter.v1.json','counter_validation':'Own public damage at7/checkpoint8 with naturally empty cache; only lease removed. Original Root failure and all previous freezes remain distinct.','independent_review_passed':False,'promoted':False,'pending':['fresh independent review/full/baseline on proposed merge','v1 source reference differences and durable/visual pending remain','whole native stage and DeadBoom outside scope'],'cleanup_deleted_bytes':sum(x['reclaimed_bytes'] for x in cleanups),'cleanup_remaining':sum(x['remaining_files'] for x in cleanups),'cleanup_errors':sum(x['error_count'] for x in cleanups),'raw_deleted':all(json.loads((OUT/n).read_bytes())['raw_deleted'] for n in ['author.initial.json','author.regression.json'])}
(OUT/'freeze.v2.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps({'core':before,'delta_files':len(delta),'groups':receipt['actual_author_groups'],'freeze_sha256':sha(OUT/'freeze.v2.json'),'cleanup_deleted_bytes':receipt['cleanup_deleted_bytes'],'cleanup_remaining':receipt['cleanup_remaining'],'cleanup_errors':receipt['cleanup_errors']}))
