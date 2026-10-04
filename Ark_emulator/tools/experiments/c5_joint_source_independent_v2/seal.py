from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/c5_joint_source_independent_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
verification=read(OUT/'verification.json');assert verification['guards_equal'] and all(x['passed'] for x in verification['results'])
pins={}
for relative in ['chapter05_predefines/runtime_ballista/module.v2.reference.json','chapter05_boss/faust/complete.v2.reference.json']:
 p=ROOT/'packages/campaign'/relative;module=read(p);pins[str(p)]=sha(p)
 for source,expected in module['manifest']['metadata'].get('source_locks',{}).items():
  actual=sha(Path(source));assert actual==expected;pins[source]=actual
b=read(ROOT/'packages/campaign/chapter05_boss/faust/branch.reference.json')
assert [len(x['actions']) for x in b['program']['phases']]==[1,1,1,1,1,2,3] and len(b['required_registrations'])==10
artifacts={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.glob('*.json'))}
helpers={str(p.relative_to(ROOT)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
report={'core':verification['core'],'source_pins_actual_verified':pins,'artifacts':artifacts,'helpers':helpers,'cases':verification['results'],'stage_audit':read(OUT/'stage_verified.json'),'scope':'Independent source composition first phase plus first valid qualified ray and public withdrawal cancellation. Ordered disk restore, full checkpoint and complete events compare with from-start public replay. Does not establish full campaign stage or actual client behavior.','preserved_old_report':'validation/campaign/c5_joint_source_independent_v1/verification.json','old_report_sha':sha(OUT.parent/'c5_joint_source_independent_v1/verification.json'),'old_report_reason':'Independent fixture expected only summon but omitted source normal/critical sequence. No candidate/module change; corrected explicit public event schema and attribute API in new v2 helper.'}
with (OUT/'freeze.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'freeze_sha':sha(OUT/'freeze.json'),'sourcepins':pins,'verification_sha':sha(OUT/'verification.json')},ensure_ascii=False))
