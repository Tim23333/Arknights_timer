"""Freeze explicit false flag author evidence; no global source or stage admission."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 out=ROOT/'packages/campaign/chapter08_consumers/special/flame_v4_joint_independent';report=out/'report.json';r=json.loads(report.read_bytes())
 assert r['status']=='passed_explicit_source_flag_author'
 module=ROOT/'packages/campaign/chapter08_consumers/flame/module.v4.joint.json'
 assert sha(module)=='fa780e59d9e47067b998a5888d44a56214644808c87b3e83493abc2b81c1762d'
 assert r['source_after']==r['module_sha256']==sha(module)
 rows=r['positive_cases']+[r['required_counter']];assert len(rows)==4 and all(x['CP750_to805'] and x['head'] and x['all_events'] for x in rows)
 assert r['required_counter']['fixed_amounts']==[390,530,710,890]
 files=[p for p in out.rglob('*') if p.is_file()]+[module,ROOT/'packages/campaign/chapter08_consumers/flame/module.v3.joint.json',ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v12.joint.json',ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v2.json',ROOT/'tools/chapter08_special/build_flame_v4_joint.py',ROOT/'tools/chapter08_special/review_flame_v4_joint.py',Path(__file__),ROOT/'tools/chapter08_flame_device/policies_v1.py',ROOT/'tools/chapter08_buff_lifetime/policies_v1.py',ROOT/'tools/chapter08_buff_lifetime/talula_providers_v1.py']
 target=out/'freeze.json';assert not target.exists()
 data={'status':'author_four_actual_source_cases_passed','runtime_core':r['core'],'module_sha256':sha(module),'pins':{str(p):sha(p) for p in files},'scope':'Only corresponding four FixedValueDamage considerUnhurtable false propagation. Other after modifier hook retained; sourceHP/SP/rays preserved. Current joint a6 and D12 actually executed, CP750 to805 and fresh replay complete event domain. No independent peer approval/global source/whole JT8-3/client verification.','old_counter_preserved':'packages/campaign/chapter08_consumers/special/flame_independent_v3/report.json','reference_policies':['neutral source targetSide2 translated to absolute player bit1, native body unverified','SP25 continuous dt0 ready749 is calibrated reference','arts damage floor .05 is reference','first DragonFire packet56 is replaceable source-reference']}
 target.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(target),'sha256':sha(target),'pins':len(data['pins'])}))
if __name__=='__main__':main()
