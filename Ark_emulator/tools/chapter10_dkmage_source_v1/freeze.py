"""Freeze full selected source body and actual bounded proof."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter10_dkmage_source_v1.build import build,SOURCE,KEY
OUT=ROOT/'validation/campaign/chapter10_dkmage_source_v1';PACKAGE=ROOT/'packages/campaign/chapter10_consumers/dkmage_source_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size}
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
core=implementation_digest();reportpath=OUT/'author.actual.v1.json';report=json.loads(reportpath.read_bytes())
assert report['actual_exit']==0 and report['core_before']==report['core_after']==core and report['source_equal']
assert len(report['results'])==4 and all(r['passed'] for r in report['results'])
assert all(sha(Path(p))==h for p,h in report['source_after'].items())
p=build();module=PACKAGE/'module.enemy_1225_dkmage_2.v1.json';write(module,p)
data=json.loads(SOURCE.read_bytes());closure=PACKAGE/'source.closure.v1.json'
write(closure,{'source':pin(SOURCE),'native_variant':data['variants'][KEY],'native_prefab':data['prefabs'][KEY],'callgraph':p['manifest']['metadata']['owned_node_mapping'],'selected_reference_policy':p['manifest']['metadata']['source_policy']})
receipt=Path('E:/ArkSimLogs/receipts/chapter10_dkmage_source_author_v1/completion.json');completed=json.loads(receipt.read_bytes());assert completed['worker_exit']==completed['cleanup_exit']==0 and completed['raw_logs_removed_after_validation']
dependencies=[ROOT/'tools/chapter10_chain_v1/native_module.py',ROOT/'tools/chapter10_chain_v1/fixture.py',ROOT/'tools/chapter10_bloodline_v1/build.py',ROOT/'validation/campaign/chapter10_chain_v1/native_source.v1.json',ROOT/'packages/campaign/chapter10_source_prepare/enemies.native.v1.json',ROOT/'packages/campaign/chapter10_source_prepare/bson.transitive.v2.json',SOURCE]
inventory={str(f.relative_to(CAND)).replace('\\','/'):sha(f) for f in sorted((CAND/'ark_sim').rglob('*')) if f.is_file() and f.suffix in ['.py','.json']}
write(OUT/'freeze.v1.json',{'schema':'ark-sim/full-source-consumer-freeze/v1','candidate':str(CAND),'core':core,'candidate_inventory':inventory,'status':'full_selected_body_authored_bounded_gates_passed_independent_pending','module':pin(module),'source_closure':pin(closure),'helpers':[pin(f) for f in sorted(Path(__file__).parent.glob('*.py'))],'dependencies':[pin(f) for f in dependencies],'actual_report':pin(reportpath),'author_groups':4,'cleanup_receipt':pin(receipt),'deleted_bytes':completed['cleanup_result']['reclaimed_bytes'],'remaining_raw':0,'cleanup_errors':0,'callgraph':p['manifest']['metadata']['owned_node_mapping'],'reference_policies':p['manifest']['metadata']['source_policy'],'interface':'tools.chapter10_dkmage_source_v1.build.build() / providers(); body unit/ch10/dkmage_source/enemy_1225_dkmage_2','composition':'Module includes six bloodline child dependencies; final stage must explicitly reconcile attribute wrapping with remaining_v2 then bind_recipients once. No native definitions/owned nodes are silently dropped.','primary_modified':False,'runtime_modified':False,'long_suite_started':False,'client_verified':False})
print(json.dumps({'freeze':pin(OUT/'freeze.v1.json'),'module':pin(module),'core':core,'cleanup_bytes':completed['cleanup_result']['reclaimed_bytes']},indent=2))
