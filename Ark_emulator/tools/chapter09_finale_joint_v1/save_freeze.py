"""Pin new joint focused evidence; no promotion or full-suite claim."""
import sys, json, hashlib, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; OUT = ROOT/'validation/campaign/chapter09_finale_joint_v1'
CAND = (ROOT/'../unpack_work/campaign_c9_finale_joint_v1_candidate').resolve()
PARENT = (ROOT/'../unpack_work/campaign_c9_mandra_v1_candidate').resolve()
sys.path.insert(0,str(CAND))
from ark_sim.adapters.api import implementation_digest
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
core = implementation_digest(); assert core == 'cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18'
parent_freeze = ROOT/'validation/campaign/chapter09_mandra_v1/freeze.final.v1.json'
frozen = json.loads(parent_freeze.read_bytes())
assert all(sha(PARENT/rel)==digest for rel,digest in frozen['source_after'].items())
reports = []
for name in ['receiver.author.v1.json','receiver.protocol.v1.json','mandra.focused.v1.json',
             'capture.focused.v1.json','catalog.focused.v1.json']:
    path = OUT/name; report = json.loads(path.read_bytes()); assert report['actual_exit']==0
    assert report.get('core',report.get('core_before'))==core
    if 'core_after' in report: assert report['core_after']==core
    for a,b in [('source_before','source_after'),('source_helpers_before','source_helpers_after')]:
        if a in report:
            assert report[a]==report[b]
            assert all(sha(Path(key))==value for key,value in report[a].items())
    reports.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'actual_exit':0,
                    'groups':len(report.get('results',[])) or 1})
source = {}; delta = []
for path in sorted((CAND/'ark_sim').rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
    rel=path.relative_to(CAND); source[rel.as_posix()]=sha(path); old=PARENT/rel
    if not old.exists() or path.read_bytes()!=old.read_bytes():
        saved=ROOT/'tools/chapter09_finale_joint_v1/source_delta'/rel
        saved.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,saved)
        delta.append({'path':rel.as_posix(),'parent_sha256':sha(old),'candidate_sha256':sha(path),
                     'saved_delta_path':saved.relative_to(ROOT).as_posix(),'saved_delta_sha256':sha(saved)})
assert len(source)==95 and {x['path'] for x in delta}=={
    'ark_sim/content/schemas.py','ark_sim/content/capabilities.py','ark_sim/domains/effects.py'}
assert sha(CAND/'ark_sim/rules/contracts.json')==frozen['catalog']['sha256']
cleanup=[]
for run in ['chapter09_finale_receiver_author_v1','chapter09_finale_receiver_protocol_v1',
            'chapter09_finale_mandra_focused_v1','chapter09_finale_capture_focused_v1','chapter09_finale_catalog_focused_v1']:
    path=Path('E:/ArkSimLogs/receipts')/run/'completion.json'; report=json.loads(path.read_bytes())
    assert report['worker_exit']==report['cleanup_exit']==0 and report['raw_logs_removed_after_validation']
    assert report['cleanup_result']['remaining_files']==report['cleanup_result']['error_count']==0
    saved=OUT/('cleanup.'+run+'.json'); saved.write_bytes(path.read_bytes())
    cleanup.append({'path':saved.relative_to(ROOT).as_posix(),'sha256':sha(saved),
                    'reclaimed_bytes':report['cleanup_result']['reclaimed_bytes'],'remaining_files':0,'error_count':0})
modules=[]
for freeze_path in [parent_freeze,ROOT/'validation/campaign/chapter09_receiver_hooks_v2/freeze.v2.json']:
    for row in json.loads(freeze_path.read_bytes())['modules']:
        path=ROOT/row['path']; expected=row.get('sha256',row.get('sha')); assert sha(path)==expected
        modules.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
after={rel:sha(CAND/rel) for rel in source}; assert source==after and core==implementation_digest()
merge=OUT/'merge.v1.json'; catalog=json.loads((OUT/'catalog.focused.v1.json').read_bytes())
receipt={'schema':'ark-sim/focused-joint-candidate-freeze/v1','candidate':str(CAND),'parent':str(PARENT),
    'parent_core':frozen['core_after'],'core_before':core,'core_after':implementation_digest(),
    'source_before':source,'source_after':after,'source_inventory_files':len(source),
    'parent_freeze':{'path':parent_freeze.relative_to(ROOT).as_posix(),'sha256':sha(parent_freeze)},
    'merge_receipt':{'path':merge.relative_to(ROOT).as_posix(),'sha256':sha(merge)},
    'source_delta':delta,'delta_files':len(delta),'reports':reports,'modules':modules,
    'catalog':{'count':108,'sha256':sha(CAND/'ark_sim/rules/contracts.json'),'old107_exact':True,'unchanged_from_mandra':True},
    'programs':catalog['programs'],
    'helpers':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'tools/chapter09_finale_joint_v1').glob('*.py'))},
    'cleanup':cleanup,'reclaimed_bytes':sum(x['reclaimed_bytes'] for x in cleanup),'remaining_files':0,'error_count':0,
    'scope':'Fresh receiver author4/protocol4, Mandra5 source profiles/tile permissions/actual HP capture/Ray public CPP-head, generic capture and exact immutable catalog108 on the new joint. Reused frozen author helpers are fresh regression evidence, not independent peer evidence.',
    'preserved':'All other92 candidate source files exactly equal frozen Mandra, including capture, skip, owned tile tasks, catalog108 and rock separate route mode. Only receiver770 deltas integrated across three conflicting files.',
    'final_freeze':True,'promoted':False,'whole_stage':False,
    'pending':['Full1219+108','Baseline','Independent joint review','9-19 complete stage assembly/run']}
path=OUT/'freeze.focused.v1.json'; assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
print(json.dumps({'core':core,'freeze':path.relative_to(ROOT).as_posix(),'freeze_sha256':sha(path),
                  'source_files':len(source),'delta_files':len(delta),'deleted_bytes':receipt['reclaimed_bytes'],'remaining':0,'errors':0}))
