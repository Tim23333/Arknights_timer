"""Static fixed-receipt audit of queue admission; launches nothing."""
import json,hashlib,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter09_elemental_successor_peer_v1';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    tool=ROOT/'tools/chapter09_elemental_successor_v1/admit_v2.py';queue=ROOT/'validation/campaign/chapter09_elemental_successor_v1/admission.queue.v2.json';before={str(p):sha(p) for p in [tool,queue,Path(__file__)]};source=tool.read_text(encoding='utf8');ast.parse(source)
    parents=[('validation/campaign/chapter09_stage_assembly/whole.admission.v6.json','ff76b105ddb6d41ea1a187619d0971374b7bcb838460e57d7a8657e0ea00aff2'),('validation/campaign/chapter09_stage919_assembly/admission.source.v4.json','455899be50505bfadcc89778b3c523807a25d6b4b96fe13addf682b86d52249f')]
    checks=[]
    for name,pin in parents:
        p=ROOT/name;assert pin in source and sha(p)==pin;d=json.loads(p.read_bytes());assert d['ready_to_execute'] is True
        assert not ('author_proofs' in d and 'actual_proofs' in d),'The source fallback must not silently drop one proof list'
        proofs=d.get('author_proofs',d.get('actual_proofs',[]));assert len(proofs)==5
        for row in proofs:
            path=Path(row['path']);path=path if path.is_absolute() else ROOT/path;assert sha(path)==row['sha256']
        checks.append({'parent':str(p),'sha256':pin,'original_proof_count':len(proofs),'original_core_identity_preserved':True})
    q=json.loads(queue.read_bytes());assert q['new_whole_runs_started'] is False and q['whole_stages_passed'] is False and q['client_verified'] is False and len(q['ready_cases'])==2
    assert all(sha(path)==value for path,value in q['consumed_receipts'].items())
    assert "parent_evidence = read(original, parent_pin)" in source and "parent_evidence['ready_to_execute'] is True" in source and "current(prefix['source_after'])" in source
    assert q['ready_cases'][0]['FIRE_business_scope']=='Actual nativeFlame/fixedLiskam3 gates' and q['ready_cases'][1]['FIRE_business_scope']=='Original package declares no native EP attack; receiver readiness only'
    after={str(p):sha(p) for p in [tool,queue,Path(__file__)]};assert before==after
    report={'schema':'ark-sim/chapter9-queue-admission-static-review/v2','tool_scope_approved':True,'source_before':before,'source_after':after,'source_equal':True,'fixed_parent_receipts':checks,'current_queue_consumed_receipts_sha_equal':True,'launch_policy':q['launch_policy'],'approved_scope':'Trusted local fixed source and bounded execution queue admission. Does not start or complete new whole run. Original mechanism receipts retain original cores.','FIRE_scope_918_only':True,'simulation_started':False,'core_or_model_approved':False,'whole_stages_approved':False,'v1_historical_weakness':'Parent mechanism receipts lacked fixedSHA/ready check; oldv1 remains preserved and is not the formal entrance.'}
    path=OUT/'admission.static.review.v2.json';assert not path.exists();path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'tool_scope_approved':True,'tool_sha256':sha(tool),'report_sha256':sha(path)}))
if __name__=='__main__':main()
