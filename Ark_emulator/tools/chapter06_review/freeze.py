import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter06_review'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((OUT/'audit.json').read_text(encoding='utf8'));plan=json.loads((ROOT/'packages/campaign/chapter06_plans/source.plan.json').read_text(encoding='utf8'))
delta=[{'path':k,'audit_start':v,'now':sha(Path(k))} for k,v in audit['guards_start'].items() if sha(Path(k))!=v]
for x in delta:assert '/chapter06/cold/' in x['path'].replace('\\','/') or '/chapter06_cold/' in x['path'].replace('\\','/')
consumed={k:v for k,v in audit['guards_start'].items() if '/chapter06/cold/' not in k.replace('\\','/') and '/chapter06_cold/' not in k.replace('\\','/')}
assert all(sha(Path(k))==v for k,v in consumed.items())
pins={}
for name,pin in plan['source_locks'].items():
 path=ROOT.parent/name;assert sha(path)==pin;pins[str(path)]=pin
report={'audit_sha':sha(OUT/'audit.json'),'public_design_sha':sha(OUT/'public_design.json'),'original_audit_guard_equal':audit['start_guard_equal'],'consumed_source_guards_now_equal':True,'consumed_source_guards':consumed,'concurrent_cold_author_changes':delta,'scope_exclusion':'Cold authors changed their build/model/test files after our source audit completed. Original audit identity kept. These partial runtime artifacts are not executed or accepted by this audit; no new Cold consumer is signed. Frozen plans/native/predefines/environment/inventory and8fa remained unchanged.','plan_source_locks_actual_verified':pins,'artifacts':{str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file()},'helpers':{str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')},'role':'Independent C6 source/API/configuration review. Four mapping data tests. Proposed public protocol is design, not full stage or core test evidence. No kernel/registry/source modifications or new whole-stage launch.'}
with (OUT/'freeze.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'freeze_sha':sha(OUT/'freeze.json'),'audit_sha':report['audit_sha'],'design_sha':report['public_design_sha'],'late_cold_deltas':len(delta)},ensure_ascii=False))
