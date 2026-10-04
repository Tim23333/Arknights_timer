"""Exclusive final author freeze receipt; no independent acceptance claim."""
from pathlib import Path
import hashlib,json,importlib.util
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m93_world_cast_leases'
spec=importlib.util.spec_from_file_location('m93_frozen_builder',Path(__file__).with_name('build.py'));b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
PIN='4e5b8d8433dd860efa57ee031e07d42e99d8799b39d78499715ba71fb12d7020'
def guard():
 roots={'candidate_source':(b.OUT/'ark_sim','*.py'),'candidate_catalog':(b.OUT/'ark_sim','*.json'),'parent_source':(b.BASE/'ark_sim','*.py'),'parent_catalog':(b.BASE/'ark_sim','*.json'),'candidate_tools':(Path(__file__).parent,'*'),'experiments':(ROOT/'tools/experiments/m93_world_cast_leases','*.py'),'compatibility_helper':(ROOT/'tools/experiments/m93_world_cast_leases_compat','*.py')}
 return {name:{str(p.relative_to(folder)):b.sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
before=guard();assert b.core(b.BASE)==b.PIN and b.core(b.OUT)==PIN
paths={name:OUT/name for name in ['composition.json','verification.json','verification_final.json','compatibility.json','compatibility_v2.json','no_feature_comparison.json']}
reports={name:json.loads(p.read_bytes()) for name,p in paths.items()}
final=reports['verification_final.json'];compat=reports['compatibility_v2.json'];cmp=reports['no_feature_comparison.json']
assert len(final['cases'])==26 and all(c['outcome']=='passed' for c in final['cases'])
assert final['core_start']==final['core_end']==PIN and final['guards_equal'] and final['reproduction_equal']
assert len(compat['cases'])==95 and all(c['outcome']=='passed' for c in compat['cases']) and compat['guards_equal']
for name in ['m93_source','m93_catalog']:
 assert final['end_manifest'][name]==compat['end_manifest'][name]
for name in ['m93_tools','m93_experiments']:
 current_name={'m93_tools':'candidate_tools','m93_experiments':'experiments'}[name]
 assert all(before[current_name].get(path)==value for path,value in final['end_manifest'][name].items())
for path,value in compat['end_manifest']['selected_tests'].items():assert b.sha(Path(path))==value
assert cmp['passed'] and cmp['all_other_values_types_and_float_bits_equal'] and len(cmp['differences'])==6
after=guard();assert before==after and b.core(b.OUT)==PIN
receipt={'role':'M93 frozen author revision, awaiting independent Root verification','parent_core':b.PIN,'core':PIN,'changed':reports['composition.json']['changed'],'start_manifest':before,'end_manifest':after,'guards_equal':True,'author_passed_cases':26,'compatibility_passed_cases':95,'fresh_rebuild_equal':True,'no_feature_complete_values_equal_except_runtime_identity':True,'report_files':{name:{'path':str(p),'sha256':b.sha(p)} for name,p in paths.items()},'policies':'World-wide cast ownership, exact same-owner idempotence, live UID validation; canonical half-open prune before atomic apply/bind; canceled/retired cast teardown and monotonic new UID after expiry; preserve removal events and stale historical lease rows','limits':['Author receipts only; original M78 independent failures remain failed','M92 DMAGE SourceCombat content fix is separate and original90e parent module is unchanged','No complete V2 suite, complete stage, 36-stage or client acceptance']}
target=OUT/'freeze.json'
with target.open('x',encoding='utf8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(json.dumps({'core':PIN,'freeze':str(target),'sha256':b.sha(target),'author_cases':26,'compatibility_cases':95}))
