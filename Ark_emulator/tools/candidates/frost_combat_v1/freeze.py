import json,hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/frost_combat_v6';RUNTIME=ROOT.parent/'unpack_work/campaign_frost_combat_v5_candidate'
spec=importlib.util.spec_from_file_location('frozen_frost_build',Path(__file__).with_name('build.py'));b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
PIN='df98feb41687d1b560d27d24bcbc7aad8bbb2f7ace48aaa67aca5816fe95e86b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guard():
 roots={'source':(RUNTIME/'ark_sim','*.py'),'catalog':(RUNTIME/'ark_sim','*.json'),'parent':(b.BASE/'ark_sim','*.py'),'tools':(Path(__file__).parent,'*'),'models':(ROOT/'packages/campaign/chapter04_boss/frost_combat_v6','*.json'),'author_helper':(ROOT/'tools/experiments/frost_combat_v6','*.py'),'compat_helper':(ROOT/'tools/experiments/frost_combat_compat','*.py')}
 return {name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern)) if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
before=guard();assert b.core(RUNTIME)==PIN and b.core(b.BASE)==b.PIN
files=[OUT/'verification_initial.json',OUT/'compatibility.json',OUT/'no_feature_comparison.json',ROOT/'validation/campaign/frost_combat_v1/composition_campaign_frost_combat_v5_candidate.json',ROOT/'packages/campaign/chapter04_boss/frost_combat_v1/source.audit.json']
a,c,n=[json.loads(p.read_bytes()) for p in files[:3]]
assert len(a['cases'])==26 and all(x['outcome']=='passed' for x in a['cases']) and a['guards_equal']
assert len(c['cases'])==182 and all(x['outcome']=='passed' for x in c['cases']) and c['fresh_rebuild_equal'] and c['source_and_module_byte_checks'] and c['guards_equal']
for key in ['source','catalog','parent','tools','models']:
 assert a['end_manifest'][key]==c['end_manifest'][key]
for path,pin in c['end_manifest']['selected_and_consumed'].items():assert sha(Path(path))==pin
assert n['passed'] and n['all_other_values_types_and_float_bits_equal'] and len(n['differences'])==6
after=guard();assert before==after and b.core(RUNTIME)==PIN
receipt={'role':'Frozen Frost normal/Blast author revision awaiting independent integration review','core':PIN,'parent_core':b.PIN,'start_manifest':before,'end_manifest':after,'guards_equal':True,'author_passed':26,'compatibility_passed':182,'fresh_rebuild_equal':True,'report_files':{str(p):sha(p) for p in files},'source_model_default':str(ROOT/'packages/campaign/chapter04_boss/frost_combat_v6/first17.bb8.reference_ground.json'),'source_model_default_sha256':'8ba0c5745735b55136fa8ba49fd277a293c0664da3701b4715594cd4139c2377','limits':['First17/zero-flight28/duration8/ground hit/cooldown pause are explicitly replaceable reference policies; native bodies pending','IceShield and multi-skill priority arbiter/shared-clock busy composition not part of this partial receipt','No full4-10/43-spawn/36-stage/client acceptance']}
target=OUT/'freeze.json'
with target.open('x',encoding='utf8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(json.dumps({'core':PIN,'freeze_sha256':sha(target),'author':26,'compatibility':182}))
