"""Correct parameter attribution using exact native raw skills, without editing frozen supplements."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=ROOT/'packages/campaign/chapter08_source_prepare/integration/enemies.native.v1.json'
 root_policy=ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.source.v1.json'
 p=json.loads(source.read_bytes());v=p['variants']['enemy_1503_talula@0/5e75f6c67ed9421f'];raw=v['native_enemy']['raw_rows'][0]['enemyData']['skills']
 result={'schema':'ark-sim/dragon-fire-source-attribution-note/v1','source_sha256':sha(source),'source_json_pointer':'variants/enemy_1503_talula@0/5e75f6c67ed9421f/native_enemy/raw_rows/0/enemyData/skills','raw_skills':raw,'resolved_skills_preserved':v['native_enemy']['resolved']['skills'],'stage_override':v['native_enemy']['stage_override'],'root_by_prefab_key_policy':{'path':str(root_policy),'sha256':sha(root_policy)},'correction':'The earlier statement that resolved exposes only DanceFire is accurate but not complete parameter attribution. The original raw rows explicitly contain DragonFire and DragonFire[Half] with duration30.5/baseDamage50/addOnDamage180/addOnDuration30 and clocks19/19 versus7/7. These values do not need to be borrowed from sktok_flame.','conflict_policy':'Whole-list resolved merge removed other raw skills; Root source policy binds overrides by prefabKey and preserves all four raw skills, explicitly replaceable until client comparison. This note does not mutate the common resolver, native source, or frozen e143 inline supplement.','runtime_authored':False,'client_verified':False}
 out=ROOT/'packages/campaign/chapter08_consumers/special/dragon_fire.raw.parameters.note.v1.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'root_policy_sha256':sha(root_policy)}))
if __name__=='__main__':main()
