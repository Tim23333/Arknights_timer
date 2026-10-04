"""Exact selected status/controller pointers; model clocks are labeled choices."""
import json,hashlib,argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));SOURCE=ROOT/'packages/campaign/chapter03_plans/source.plan.json';PIN='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6';OUT=ROOT/'packages/campaign/chapter03_visibility/source.reference.json';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build():
 raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==PIN;d=json.loads(raw)
 for name,pin in d['source_locks'].items():assert sha(ROOT.parent/name)==pin
 prefabs=d['selected_native_prefabs'];lurker=prefabs['enemy_1009_lurker'];toggle=lurker['components']['1815641500334631868'];checker=lurker['components'][str(toggle['raw']['_checker']['m_PathID'])]
 assert toggle['raw']['_buffs'][0]['attributes']['abnormalFlags']==[9] and checker['raw']['_isInitToggled']==1 and checker['raw']['_disableWhenAttack']==1 and checker['raw']['_disableWhenBlocked']==1 and checker['raw']['_restoreDelay']==3
 skill=prefabs['sktok_sensor'];aura=next(c for c in skill['components'].values() if c['native_class']=='AuraAbility');validator=skill['components'][str(aura['raw']['_targetValidator']['m_PathID'])];assert aura['raw']['_buffs'][0]['attributes']['abnormalImmunes']==[9] and validator['raw']['_targetOptions']['ignoreTargetFree']==1
 from tools.build_chapter01_enemy_sources import NativeAssets
 from tools.build_chapter02_enemy_sources import exact_shared_skeleton
 from tools.extract_campaign_animation_bindings import library_identity,resolve_animation
 before=library_identity();animation=exact_shared_skeleton('enemy_1009_lurker',ROOT.parent/lurker['source']['path'],NativeAssets());assert before==library_identity()
 attack=next(c for c in lurker['components'].values() if c['native_class']=='MeleeAttack');binding=resolve_animation(attack['raw']['_animKey'],animation['animator']['fields']['_animations'],animation['parsed'])
 locks=dict(d['source_locks']);locks[animation['source']['path']]=animation['source']['sha256']
 return {'schema':'ark-sim/chapter03-visibility-source/v1','source_plan_sha256':PIN,'source_locks':locks,'builder_sha256':sha(__file__),'private_spine_reader_identity':before,'lurker':{'prefab_source':lurker['source'],'toggle':toggle,'checker':checker,'attack':attack,'attack_binding':binding,'animation':animation,'resolved_variants':{k:v for k,v in d['variants'].items() if 'enemy_1009_lurker@' in k}},'sensor':{'source':prefabs['trap_005_sensor']['source'],'self_passive':next(c for c in prefabs['trap_005_sensor']['components'].values() if c['native_class']=='PassiveBuffAbility'),'skill_aura':aura,'target_validator':validator,'table':d['predefined_table_subsets']['trap_005_sensor']},'enum':d['abnormal_enum'],'declared_model':{'initial_toggle':True,'held_off':'actual existing live blocker','restore_from_hold_release_seconds':3,'pulse_event':'attack.accepted source-owner, one accepted attack cast; selectable profile, exact native OnAttack/checker method body not recovered','immunity':'live abnormal_immunes masks same flag only, retains underlying controller/child Buff','targeting':'explicit candidate availability binding/visibility flag parameter9; source-relative side and exact sensor bypass9 content policy; not camouflage17'},'feedback_pending':['checker event/body restore clock correspondence','20250327 sensor assets versus20260929 fixed tables','native anti/immunity ordering and target-free getter mapping'],'runtime_created':False,'formal_approved':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();v=build();raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==raw
 else:OUT.write_bytes(raw)
 print(json.dumps({'passed':True,'sha256':sha(OUT)}))
