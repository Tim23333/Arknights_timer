"""Fresh bounded peer report; no approval or stage claim."""
import sys,json,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=Path(os.environ.get('ARKSIM_PEER_ROOT',str(ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate')))
sys.path.insert(0,str(RUNTIME));sys.path.insert(0,str(Path(__file__).parent))
import test_peer as peer
from ark_sim.adapters.api import implementation_digest
import ark_sim,pytest,UnityPy
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit_path=ROOT/'validation/campaign/advanced_selector_source_audit.json'
audit=json.loads(audit_path.read_bytes());locks={str(audit_path):sha(audit_path),str(Path(__file__)):sha(__file__),str(Path(peer.__file__)):sha(peer.__file__)}
for row in audit['actual_selectors']:
 path=ROOT.parent/row['source']['path'];assert sha(path)==row['source']['sha256'];locks[str(path)]=sha(path)
 objs={o.path_id:o for o in UnityPy.load(str(path)).objects}
 assert objs[row['actual_component_path_id']].read_typetree()==row['raw']
expected={'campaign_m26_decision_eligibility_candidate':'7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe','campaign_m25_eligibility_candidate':'281dc1fc3fc35e83adad37146b2bfb16afa92c5086f29fc22e881f116eb80ace','campaign_m23_roster_candidate':'0258f171d31daffb7b917e2ebad2603505e5fa762e99ef4a71b3b30342d62381'}
core_start=implementation_digest();assert core_start==expected[RUNTIME.name]
args=[str(Path(peer.__file__)),'-q']
if 'm23' in RUNTIME.name:args+=['-k','public_deploy or absent_roster or owned_spawn']
if 'm25' in RUNTIME.name:args+=['-k','standalone']
start={p:sha(p) for p in locks};exit_code=pytest.main(args)
end={p:sha(p) for p in locks};core_end=implementation_digest()
label=RUNTIME.name.split('_')[1];out=ROOT/f'validation/campaign/{label}_peer/final.json';out.parent.mkdir(parents=True,exist_ok=True)
report={'schema_version':1,'scope':'independent mechanism peer only; not native correctness, promotion, receipt or stage','passed':exit_code==0 and start==end and core_start==core_end,'pytest_exit_code':int(exit_code),'runtime_root':str(RUNTIME),'actual_module':ark_sim.__file__,'core_start':core_start,'core_end':core_end,'source_helper_start':start,'source_helper_end':end,'actual_source_typetrees_checked':len(audit['actual_selectors']),'fixtures':peer.INPUTS,'native_body_client_pending':True,'fixture_failures_preserved_description':['open roster positive originally removed every reachable target reference and compiler correctly pruned it; corrected to declared dormant initial target','owned spawn initially put parameter fields at effect root; schema rejected; then skill payload position initially outside payload; corrected public command shape'],'formal_approval':False}
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':report['passed'],'fixtures':len(peer.INPUTS),'report':str(out),'sha256':sha(out)}));raise SystemExit(0 if report['passed'] else 1)
