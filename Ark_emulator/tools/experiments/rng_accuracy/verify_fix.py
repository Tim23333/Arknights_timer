import sys,json,hashlib,subprocess,os,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];LIVE=ROOT.parent/'tools/ak_live_rng';OUT=ROOT/'validation/campaign/rng_accuracy';OLD=OUT/'original_helper'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[LIVE/n for n in ['rng_engines.py','tracker.py','rng_service.py','memscan.py','README.md','test_ak_live_rng.py']];locks={str(p):sha(p) for p in paths};env={**os.environ,'PYTHONIOENCODING':'utf-8'}
commands=[[sys.executable,'-m','pytest','tools/experiments/rng_accuracy/test_full_cursor.py','-q'],[sys.executable,str(LIVE/'test_ak_live_rng.py')]];runs=[]
for name,command in zip(['independent','existing'],commands):
 r=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8');(OUT/(name+'.log')).write_text(r.stdout,encoding='utf8');assert r.returncode==0,r.stdout
 runs.append({'command':command,'returncode':r.returncode,'output_path':'validation/campaign/rng_accuracy/'+name+'.log','output_sha256':sha(OUT/(name+'.log')),'observed_summary':r.stdout.splitlines()[-1]})
assert '11 passed' in (OUT/'independent.log').read_text(encoding='utf8') and '69' in (OUT/'existing.log').read_text(encoding='utf8')
assert {str(p):sha(p) for p in paths}==locks
patch=[];changed=[]
for path in paths:
 old=OLD/path.name
 if sha(old)!=sha(path):
  changed.append({'path':str(path),'old_sha256':sha(old),'new_sha256':sha(path),'old_bytes':str(old)})
  patch.extend(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),path.read_text(encoding='utf8').splitlines(True),fromfile='a/tools/ak_live_rng/'+path.name,tofile='b/tools/ak_live_rng/'+path.name))
(OUT/'helper_fix.patch').write_text(''.join(patch),encoding='utf8');oldreport=OUT/'source_audit.json'
result={'schema':'ark-sim/rng-full-cursor-recovery-fix/v1','passed':True,'device_access_performed':False,'original_source_audit':{'path':'validation/campaign/rng_accuracy/source_audit.json','sha256':sha(oldreport)},'original_source_archive_sha256':sha(OLD/'source.json'),'source_locks_start':locks,'source_locks_end':{str(p):sha(p) for p in paths},'runs':runs,'changed_files':changed,'patch_sha256':sha(OUT/'helper_fix.patch'),'tests':{'independent':11,'existing_fake_memory_checks':69},'expectations':['valid separation21/31 including wrapped70/120draw state recovery','legally readable observedp32 rejected solely because full endpoint differs','old cursor state kept/status lost when recovery fails','incomplete Knuth endpoint explicit error','MT700draw/twist unchanged'],'scope':'complete double cursor recovery matching only; no seed constructor/algorithm/stream mapping replacement','client_accuracy_verified':False,'formal_approval':False};(OUT/'helper_fix.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'independent':11,'existing':69,'report_sha256':sha(OUT/'helper_fix.json'),'patch_sha256':sha(OUT/'helper_fix.patch')}))
