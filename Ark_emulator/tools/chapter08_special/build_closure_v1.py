"""Exact two-special native closure plus independently versioned flame BB supplement."""
import hashlib,json
from pathlib import Path
from tools.chapter08_special.recursive_source_v1 import closure
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'packages/campaign/chapter08_source_prepare/integration'
OUT=ROOT/'packages/campaign/chapter08_consumers/special'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def walk(v,path=''):
 yield path,v
 if isinstance(v,dict):
  for k,x in v.items():yield from walk(x,path+'/'+str(k))
 elif isinstance(v,list):
  for i,x in enumerate(v):yield from walk(x,path+'/'+str(i))
def main():
 paths=[SOURCE/n for n in ['source.manifest.v1.json','mechanism.plan.v1.json','source.plan.v1.json','enemies.native.v1.json','buffs.typed.v3.json','source.supplement.v1.json']]
 before={str(p):sha(p) for p in paths};p=json.loads((SOURCE/'enemies.native.v1.json').read_bytes())
 variants={k:v for k,v in p['variants'].items() if v['native_reference']['id'] in ('enemy_1112_emppnt','enemy_1113_empace')}
 assert set(variants)=={'enemy_1112_emppnt@0/4f469bc1099e78dd','enemy_1113_empace@0/1fc76d096d0bb1df'}
 keys={v['prefab_key'] for v in variants.values()};prefabs={k:p['prefabs'][k] for k in keys};projectiles={k:p['projectiles'][k] for k in ('projectile_enemy_emppnt','projectile_enemy_empace')}
 scriptkeys={n['script_key'] for g in [*prefabs.values(),*projectiles.values()] for n in g['components'].values() if n.get('script_key')}
 script_refs={k:v for k,v in p['native_monoscripts'].items() if k in scriptkeys}
 result={'schema':'ark-sim/chapter08-special-native-closure/v1','fixed_commit':'56aee3d6c5a29c3a0d192456d70d14252cbb0804','guards_before':before,'variants':variants,'prefabs':prefabs,'animations':{k:p['animations'][k] for k in keys},'projectiles':projectiles,'native_monoscripts':script_refs,'script_key_dependency_set':sorted(scriptkeys),'bson_empty':p['bson_templates']['templates']['empty'],'inline_buff_policy':'loadFromDB0 stays inline; native empty BSON is actually parsed with no actions. Visual-only Buff presence retained; DB missing inline names never creates guessed gameplay.','external_selector_buff_dependency':'mark_neutral[effect] is a target-priority marker, not a fabricated same-owner passive; absent markers use explicit fallback policy.','runtime_authored':False,'client_verified':False,'builder_sha256':sha(Path(__file__))}
 result['guards_after']={str(q):sha(q) for q in paths};assert result['guards_after']==before
 OUT.mkdir(parents=True,exist_ok=True);target=OUT/'source.closure.v1.json';assert not target.exists();target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
 hits=[{'source_pointer':path,'inline_buff':v} for path,v in walk(p['prefabs']) if isinstance(v,dict) and v.get('buffKey')=='dragon_fire']
 supplemental={'schema':'ark-sim/dragon-fire-inline-parameter-supplement/v1','enemies_source_sha256':sha(SOURCE/'enemies.native.v1.json'),'recursive_DB_BSON_sha256':sha(OUT/'dragon_fire.supplement.v1.json'),'inline_references':hits,'runtime_authored':False}
 st=OUT/'dragon_fire.inline.parameters.v1.json';assert not st.exists();st.write_bytes((json.dumps(supplemental,ensure_ascii=False,indent=2)+'\n').encode())
 print(json.dumps({'closure_sha256':sha(target),'scripts_found':len(script_refs),'script_dependency_count':len(scriptkeys),'flame_inline_parameter_sha256':sha(st),'flame_inline_references':len(hits)}))
if __name__=='__main__':main()
