"""Seal independently completed actual evidence; never relabel old results."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
out=ROOT/'validation/campaign/campaign_owned_dead_callback_peer_v1'
report=out/'actual.v3.json';r=json.loads(report.read_bytes())
assert r['actual_exit']==0 and r['source_equal'] and len(r['results'])==8 and all(x['passed'] for x in r['results'])
assert all(sha(p)==pin for p,pin in r['source_after'].items())
clean=[]
for i in [1,2,3]:
 p=Path('E:/ArkSimLogs/receipts')/f'dead_callback_peer_737_v{i}/completion.json';c=json.loads(p.read_bytes());assert c['cleanup_exit']==0 and c['raw_logs_removed_after_validation'] and c['cleanup_result']['error_count']==c['cleanup_result']['remaining_files']==0
 clean.append({'path':str(p),'sha256':sha(p),'worker_exit':c['worker_exit'],'reclaimed_bytes':c['cleanup_result']['reclaimed_bytes'],'remaining_files':0,'errors':0})
files=[p for p in (ROOT/'tools/campaign_owned_dead_callback_peer_v1').glob('*') if p.is_file()]+[p for p in out.glob('*') if p.is_file()]
receipt={'schema':'ark-sim/independent-owned-dead-callback-freeze/v1','core':r['core'],'actual_report':str(report),'actual_report_sha256':sha(report),'actual_groups':8,'actual_exit':0,'all_current_source_guards_equal':True,'files':{str(p):sha(p) for p in files},'full_disk_CPP_public_head_proofs':{k:v for k,v in r['facts'].items() if isinstance(v,dict) and v.get('CP_head_equal')},'cleanup':clean,'total_reclaimed_bytes':sum(x['reclaimed_bytes'] for x in clean),'no_live_peer_process':True,'historical_failure':'actual.v1 preserves invalid fixture field applicability; source API active_rule corrected in later fresh report. No kernel counter found.','scope':'Generic synchronous captured callback only. Does not approve dmech consumer, primary promotion, whole stage or client equivalence.'}
p=out/'final.freeze.v1.json';assert not p.exists();p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps({'freeze_sha256':sha(p),'raw_reclaimed':receipt['total_reclaimed_bytes'],'CPP_head_proofs':len(receipt['full_disk_CPP_public_head_proofs'])}))
