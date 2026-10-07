"""Freeze three source consumers; explicitly keep dmech unsupported."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_joint_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter10_stage17_ordinary_v1.build import build,source,SOURCE,BSON
OUT=ROOT/'validation/campaign/chapter10_stage17_ordinary_v1';PACKAGE=ROOT/'packages/campaign/chapter10_consumers/stage17_ordinary';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size}
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
report_path=OUT/'author.final.v4.json';report=json.loads(report_path.read_bytes());core=implementation_digest();assert report['actual_exit']==0 and report['source_equal'] and report['core_before']==report['core_after']==core
assert all(sha(Path(path))==h for path,h in report['source_after'].items())
modules=[];policies={}
for key in ['enemy_1229_darmy','enemy_1228_dslime','enemy_1226_dklord']:
    p=build(key);file=PACKAGE/(key+'.module.v1.json');write(file,p);modules.append(pin(file));policies[key]=p['manifest']['metadata']['reference_policy']
v,pref=source('enemy_1226_dklord');options=next(c['raw']['_targetOptions'] for c in pref['components'].values() if c['native_class']=='FilterBuffTargetValidator')
cfg=next(s for s in build('enemy_1226_dklord')['selectors'] if s['id']=='selector/ch10/stage17_ordinary/lord_aura')['eligibility']['parameters']['source_configuration']
for key in ['targetSide','targetMotion','targetCategory','ignoreTargetFree','ignoreAllyTargetFree','ignoreHealFree','ignoreMotionMode','excludeSomeAbnormalFlags','excludeAbnormalFlag','professionMask','checkUnitType','unitTypeMask','onlyIgnoreSomeOfTargetFreeCase','abnormalFlag','abnormalCombo']:assert type(cfg['_'+key]) is type(options[key]) and cfg['_'+key]==options[key]
receipts=[]
for version in range(1,5):
    f=Path('E:/ArkSimLogs/receipts')/('chapter10_stage17_ordinary_author_v'+str(version))/'completion.json';r=json.loads(f.read_bytes());assert r['cleanup_exit']==0 and r['raw_logs_removed_after_validation'];receipts.append({**pin(f),'worker_exit':r['worker_exit'],'cleanup':r['cleanup_result']})
deps=[SOURCE,BSON,ROOT/'tools/chapter10_bloodline_v1/build.py',ROOT/'tools/chapter10_remaining_v1/build.py',ROOT/'tools/campaign_elemental_receivers_v1/build.py']
write(OUT/'freeze.v1.json',{'schema':'ark-sim/source-ordinary-selected-consumers-freeze/v1','status':'three_consumers_authored_actual_passed_dmech_core_gap_pending','core':core,'candidate':str(CAND),'candidate_inventory':{str(p.relative_to(CAND)).replace('\\','/'):sha(p) for p in sorted((CAND/'ark_sim').rglob('*')) if p.is_file() and p.suffix in ['.py','.json']},'modules':modules,'helpers':[pin(p) for p in sorted(Path(__file__).parent.glob('*.py'))],'dependencies':[pin(p) for p in deps],'actual_report':pin(report_path),'groups':4,'lifesteal_boundaries':['overkill25 -> heal55','absorbed barrier primary HP0 -> heal0','invincible primary HP0 -> heal0','postRES22.5 -> heal49.5'],'native_method_body_verified':False,'policies':policies,'base_lord_native_target_options_typed_equal':True,'dmech_counter':pin(OUT/'dmech.channel.counter.v1.json'),'dmech_requirements':pin(PACKAGE/'dmech.generic.requirements.v1.json'),'PRTS_dmech_reference':pin(PACKAGE/'dmech.reference.v1.json'),'dmech_runtime_implemented':False,'overall_four_consumer_complete':False,'cleanup':receipts,'deleted_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts),'remaining_raw':0,'errors':0,'prior_failed_reports':[pin(OUT/('author.actual.v'+str(i)+'.json')) for i in [1,2]],'prior_passed_identity_not_migrated':pin(OUT/'author.actual.v3.json'),'primary_changed':False,'core_changed':False,'simulation_whole_stage_executed':False,'independent_approved':False,'interface':'tools.chapter10_stage17_ordinary_v1.build.build(key), providers(); exact3 source keys only; dmech intentionally raises required capability gap.'})
print(json.dumps({'freeze':pin(OUT/'freeze.v1.json'),'modules':modules,'cleanup_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts),'core':core},indent=2))
