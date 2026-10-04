import json,hashlib,sys
from pathlib import Path
import UnityPy
ROOT=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
 path=ROOT/'packages/campaign/chapter01_sources/native.reference.json';normal=ROOT/'packages/campaign/chapter01_models/w_combat/native.reference.json'
 assert sha(path)=='a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd' and sha(normal)=='e182463277369f7ddd9a377e038ef30476a3d96c24daf4ee977bfe50c8b0fe5c'
 source=json.loads(path.read_bytes());cache={};records=[];locks={str(path):sha(path),str(normal):sha(normal)}
 def objs(record):
  p=ROOT.parent/record['path'];assert sha(p)==record['sha256'];locks[str(p)]=sha(p)
  if p not in cache:cache[p]={o.path_id:o for o in UnityPy.load(str(p)).objects}
  return cache[p]
 for key in ('projectile_enemy_cqbw','projectile_enemy_cqbw_s1'):
  p=source['projectiles'][key];o=objs(p['source']);assert o[p['root_gameobject_path_id']].read_typetree()['m_Name']==key
  for pid,c in p['components'].items():
   if c['native_class'] not in ('SimpleProjectile','ParacurveMovement','AttachToTarget'):continue
   raw=o[int(pid)].read_typetree();assert raw==c['raw']
   script=source['native_monoscripts'][c['script_key']];actual=objs(script['source'])[script['path_id']].read_typetree();assert actual==script['raw'] and actual['m_ClassName']==c['native_class']
   records.append({'projectile_key':key,'asset':p['source'],'root_gameobject_path_id':p['root_gameobject_path_id'],'component_path_id':int(pid),'actual_native_class':actual['m_ClassName'],'script_PPtr':raw['m_Script'],'MonoScript_source':script['source'],'MonoScript_path_id':script['path_id'],'actual_typetree':raw})
 w=source['enemies']['enemy_1504_cqbw'];o=objs(w['prefab']['source']);attacks=[]
 for pid,c in w['prefab']['components'].items():
  if c['raw'].get('_projectileKey') not in ('projectile_enemy_cqbw','projectile_enemy_cqbw_s1'):continue
  raw=o[int(pid)].read_typetree();assert raw==c['raw'];attacks.append({'path_id':int(pid),'raw':raw})
 result={'schema':'ark-sim/chapter01-projectile-source-audit/v1','passed':True,'source_locks':[{'path':p,'sha256':h} for p,h in locks.items()],'actual_projectile_components':records,'actual_RangedAttack_components':attacks,'native_DB_skill':w['native_enemy']['resolved']['skills'],'method_bodies_recovered':False,'source_boundary':'Raw components/PPtr/MonoScript are actual re-reads; callback/curve/area/parent transform bodies remain unknown','tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(Path(__file__)),'result':'passed'}]}
 out=ROOT/'packages/campaign/chapter01_models/projectile_lifecycle/source.reference.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({'passed':True,'projectile_components':len(records),'RangedAttack':len(attacks)}))
if __name__=='__main__':run()
