import json,sys,subprocess,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';OUT=ROOT/'validation/campaign/chapter06_runner_independent';OUT.mkdir(exist_ok=False)
RUNNER=ROOT/'tools/run_campaign_disk_runthrough_v16.py';HELPER=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py';PROVIDERS=ROOT/'tools/chapter06_review/runner_providers_v1.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[RUNNER,ROOT/'tools/run_campaign_disk_runthrough_v15.py',HELPER,PROVIDERS,HERE/'input.json',HERE/'commands.json',Path(__file__),ROOT/'tools/chapter06/cold/policies.py',ROOT/'tools/chapter06_npcs/providers_v2.py',ROOT/'tools/chapter06_npcs/policies.py',ROOT/'tools/chapter06_npcs/huang_v6_policy.py',ROOT/'tools/chapter06_npcs/amiya_policy.py',ROOT/'tools/campaign_ordered_checkpoint.py',ROOT/'tools/campaign_streaming_evidence.py']+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ['.py','.json']]
def guards():return {str(p):sha(p) for p in sorted(paths)}
before=guards();cases=[]
def run(name,module,pin=None,omit=False):
 args=[sys.executable,str(RUNNER),'--runtime-root',str(RUNTIME),'--package',str(HERE/'input.json'),'--commands',str(HERE/'commands.json'),'--output',str(OUT/(name+'.json')),'--evidence-helper',str(HELPER),'--expected-core','fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b','--helper-sha256',sha(HELPER),'--max-ticks','120','--checkpoint-at','8']
 if not omit:args+=['--providers-module',str(module),'--providers-sha256',pin or sha(module)]
 start=sha(module);p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True);path=OUT/(name+'.json');report=json.loads(path.read_bytes()) if path.exists() else None
 row={'case':name,'argv':args,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'module_hash_before':start,'module_hash_after':sha(module),'actual_report':report};cases.append(row);return row
positive=run('good',PROVIDERS);positive['expected_pass']=True;positive['passed']=positive['exit']==0 and positive['actual_report']['passed']
for name,module,pin,omit in [('missing_module_cli',PROVIDERS,None,True),('wrong_pin',PROVIDERS,'0'*64,False),('missing_required_provider',HERE/'missing.py',None,False)]:
 r=run(name,module,pin,omit);r['expected_reject']=True;r['passed']=r['exit']!=0
r=run('valid_evaluate_declaration',HERE/'evaluate.py');r['expected_pass']=True;r['passed']=r['exit']==0
r=run('provider_changes_own_source_after_pin',HERE/'self_mutating.py');r['expected_reject']=True;r['passed']=r['exit']!=0 or not (r['actual_report'] or {}).get('passed');r['gap_if_passed']=r['exit']==0 and (r['actual_report'] or {}).get('passed',False)
after=guards();report={'core':'fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b','cases':cases,'passed':sum(r['passed'] for r in cases),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Independent CLI/provider identity guards and short one-enemy disk execution; no campaign stage coverage. All mutation confined to new peer self_mutating.py.'}
with (OUT/'verification.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps({'cases':len(cases),'passed':report['passed'],'sha':sha(OUT/'verification.json'),'failures':[r['case'] for r in cases if not r['passed']],'guards_equal':before==after}))
