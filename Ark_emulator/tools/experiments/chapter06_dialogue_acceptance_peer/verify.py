import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.campaign_public_dialogue_validation import validate as dialogue
from tools.campaign_runthrough_progress_v4 import inspect,validate_native_overlay
OUT=ROOT/'validation/campaign/chapter06_dialogue_acceptance_independent';OUT.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
entrypath=ROOT/'validation/campaign/chapter06_story_complete_pending_v3/entry.json';entry=json.loads(entrypath.read_bytes());package_path=ROOT/entry['package'];parent_path=ROOT/entry['parent_package'];commands_path=ROOT/entry['commands'];report_path=Path(entry['report']);package=json.loads(package_path.read_bytes());parent=json.loads(parent_path.read_bytes());commands=json.loads(commands_path.read_bytes());report=json.loads(report_path.read_bytes());saved_path=Path(report['driver_checkpoint']['path']);saved=json.loads(saved_path.read_bytes())
files=[Path(__file__),ROOT/'tools/campaign_public_dialogue_validation.py',ROOT/'tools/campaign_runthrough_progress_v4.py',ROOT/'tools/campaign_runthrough_progress_v3.py',ROOT/'tools/campaign_runthrough_progress_v2.py',ROOT/'tools/campaign_runthrough_progress.py',ROOT/'tools/compare_campaign_trace.py',entrypath,package_path,parent_path,commands_path,report_path,saved_path,Path(report['checkpoint']),Path(report['journal']['path']),Path(report['continuation_journal']['path']),Path(report['replayed_journal']['path']),Path(report['checkpoint_event_reference']['path']),Path(report['journal']['path']).with_name(Path(report['journal']['path']).name.replace('.events.jsonl','.replay.json'))]
def guards():return {str(p):sha(p) for p in files}
before=guards();rows=[];inputs=[]
actual=inspect(ROOT,entry);assert actual['process_status']=='complete' and actual['determinism_status']=='verified' and actual['public_dialogue']['actual_dialogue_acks']==7 and actual['public_dialogue']['native_controls_completed']==5 and actual['public_dialogue']['native_predefined_activations']==3 and actual['public_dialogue']['actual_player_deployments']==0 and commands==[];rows.append({'case':'actual_entry_empty_input_real7ack_complete','passed':True,'actual':actual})
def reject(name,fn,input):
 inputs.append({'case':name,'input':input})
 try:v=fn()
 except (ValueError,KeyError,TypeError,OSError) as e:rows.append({'case':name,'passed':True,'rejection':str(e)})
 else:rows.append({'case':name,'passed':False,'unexpected_acceptance':v})
for name,change in [('forged_control',lambda r:r['driver_final']['submitted'][0].update(control='control/foreign')),('bool_step',lambda r:r['driver_final']['submitted'][0].update(step=False)),('duplicate_ledger_event',lambda r:r['driver_final']['submitted'].append(deepcopy(r['driver_final']['submitted'][0]))),('wrong_final_clock',lambda r:r['driver_final'].update(at=r['end_tick']+1)),('wrong_final_cursor',lambda r:r['driver_final'].update(cursor=r['journal']['events']-1)),('sidecar_bad_pin',lambda r:r['driver_checkpoint'].update(sha256='0'*64)),('late_submission',lambda r:r['driver_final']['submitted'][0].update(submitted_at=99,at=100))]:
 r=deepcopy(report);change(r);reject(name,lambda r=r:dialogue(ROOT,package,commands,r),r)
for name,change in [('saved_cursor_bool',lambda d:d.update(cursor=True)),('saved_future_ledger',lambda d:d.update(submitted=deepcopy(report['driver_final']['submitted']))),('saved_missing_await',lambda d:d.update(submitted=[])),('saved_wrong_clock',lambda d:d.update(at=301))]:
 d=deepcopy(saved);change(d);path=OUT/(name+'.driver.json');path.write_text(json.dumps(d,indent=2),encoding='utf8');r=deepcopy(report);r['driver_checkpoint']={'path':str(path),'sha256':sha(path)};reject(name,lambda r=r:dialogue(ROOT,package,commands,r),r)
for name,change in [('hidden_made_visible',lambda p:p['scenarioDraft']['initialEntities'][1].update(active=True)),('control_count_pollution',lambda p:next(a for w in p['scenarioDraft']['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='control').update(count=2)),('profile_birth_bool',lambda p:p['scenarioDraft']['metadata']['runthrough_profile'].update(source_births=True)),('profile_slot_bool',lambda p:p['scenarioDraft']['metadata']['runthrough_profile'].update(deploy_capacity=False))]:
 p=deepcopy(package);change(p);reject(name,lambda p=p:validate_native_overlay(p,parent,commands_path),p)
foreign=[{'at':10,'action':'skill','source':'foreign','ability':'unknown'}];reject('foreign_public_input',lambda:dialogue(ROOT,package,foreign,report),foreign)
# Report enum/counter shape should not silently compare1 andTrue, or0 andFalse.
for name,change in [('expected_births_bool',lambda r:r['expected_births'].update({next(iter(r['expected_births'])):True})),('state_counts_bool',lambda r:r['state'].update(kills=True,leaks=False,pending_waves=False))]:
 r=deepcopy(report);change(r);path=OUT/(name+'.report.json');path.write_text(json.dumps(r,indent=2),encoding='utf8');e=deepcopy(entry);e['report']=str(path);inputs.append({'case':name,'input':r});result=inspect(ROOT,e);rows.append({'case':name,'passed':result['process_status']=='stale_or_invalid','actual':result})
after=guards();proof={'cases':rows,'passed':sum(r['passed'] for r in rows),'guards_start':before,'guards_end':after,'guards_equal':before==after,'scope':'Independent actualempty commands source entry + hostile driver/sidecar/prefix/type/hidden/count/public command provenance. Only new copies modified; no simulation/new whole or registry write.'}
for name,obj in [('inputs.json',inputs),('verification.json',proof)]:
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
print(json.dumps({'cases':len(rows),'passed':proof['passed'],'sha':sha(OUT/'verification.json'),'guards_equal':before==after,'failures':[r['case'] for r in rows if not r['passed']]}))
