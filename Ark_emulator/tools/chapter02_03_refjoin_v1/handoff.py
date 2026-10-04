import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'validation/campaign/chapter02_03_refjoin_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
preparation=read(OUT/'preparation.json');prefix=read(OUT/'prefix_verification.json');native=read(OUT/'native_audit.json')
assert prefix['guards_equal'] and all(x['passed'] for x in prefix['results']) and all(x['passed'] for x in native['results'])
for path,pin in preparation['guard_start'].items():assert sha(Path(path))==pin
runner=ROOT/'tools/run_campaign_disk_runthrough_v15.py';helper=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py';hp=sha(helper)
assert hp=='2029677af14d702ef917522be3dd2d348b906366759905af41e6562399df29e9'
plans=[]
for r in preparation['results']:
 out=Path('E:/ArkSimEvidence/campaign')/(r['stage'].replace('-','_')+'_8fa_refjoin_v1')/'full_v1.json'
 argv=[str(ROOT.parent/'.venv/Scripts/python.exe'),str(runner),'--runtime-root',preparation['runtime'],'--expected-core',preparation['core'],'--package',r['life_package'],'--commands',r['commands'],'--output',str(out),'--evidence-helper',str(helper),'--helper-sha256',hp,'--max-ticks','30000','--checkpoint-at','700']
 plans.append({'stage':r['stage'],'argv':argv,'package_sha':r['life_sha'],'commands_sha':r['commands_sha'],'proposed_output':str(out),'launch_authorized_here':False,'launched':False,'scheduling':'Root independently reviews preparation/prefix then selects scheduling; this file does not execute or reserve output.'})
artifacts={str(p.relative_to(ROOT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
helpers={str(p.relative_to(ROOT)):sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
support={str(p.relative_to(ROOT)):sha(p) for p in [runner,helper,ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v13.py',ROOT/'tools/candidates/m71_event_storage/campaign_streaming_evidence_v12.py']}
report={'core':preparation['core'],'prepared_inputs':preparation['results'],'prefix_receipt_sha':sha(OUT/'prefix_verification.json'),'native_audit_sha':sha(OUT/'native_audit.json'),'preparation_sha':sha(OUT/'preparation.json'),'planned_root_argv':plans,'evidence_artifacts':artifacts,'author_helpers':helpers,'future_runner_support':support,'full_stage_started':False,'old_checkpoint_migration':False,'role':'Author new input preparation, source audits and220tick prefixes; requires Root independent review. No claim of whole-stage completion or client match.'}
with (OUT/'freeze.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'freeze':str(OUT/'freeze.json'),'sha':sha(OUT/'freeze.json'),'prefix_sha':sha(OUT/'prefix_verification.json'),'native_audit_sha':sha(OUT/'native_audit.json'),'plans':plans},ensure_ascii=False))
