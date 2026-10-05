"""All source-used chapter10 tile assets/raw operands, no terrain consumer claim."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter07.native_assets_v1 import NativeAssets,find_templates,bson_source
from tools.build_chapter02_enemy_sources import geometry_source
PLAN=ROOT/'packages/campaign/chapter10_source_prepare/source.plan.v1.json';PIN='08fa62a25e4c42658e2377ebdbd701c9690820c6d964f701df1d418d6b3b9d60';OUT=ROOT/'packages/campaign/chapter10_source_prepare/environment.native.v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 import UnityPy
 assert sha(PLAN)==PIN;plan=json.loads(PLAN.read_bytes());assets=NativeAssets();keys={t['tileKey'] for s in plan['stages'].values() for t in s['native_document']['mapData']['tiles']};paths={k:[] for k in sorted(keys)}
 for p in (ROOT.parent/'data/battle/prefabs').glob('*tiles.ab_unpacked/CAB-*'):
  if p.name.endswith('.resS'):continue
  for o in UnityPy.load(str(p)).objects:
   if o.type.name=='GameObject' and o.read().m_Name in keys:paths[o.read().m_Name].append(p)
 prefabs={};templates=set()
 for k,found in paths.items():
  if len(found)!=1:prefabs[k]={'status':'exact_tile_asset_missing_or_ambiguous','candidate_paths':[str(p) for p in found]};continue
  prefabs[k]=assets.closure(found[0],k);prefabs[k]['geometry_sources']=geometry_source(assets,prefabs[k]);templates|=find_templates(prefabs[k])
 bson=bson_source(templates);locks={PLAN.relative_to(ROOT.parent).as_posix():PIN}
 def collect(v):
  if isinstance(v,dict):
   if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):locks[v['path']]=v['sha256']
   for x in v.values():collect(x)
  elif isinstance(v,list):
   for x in v:collect(x)
 collect(prefabs);collect(bson);collect(assets.scripts)
 for p in (Path(__file__),ROOT/'tools/chapter07/native_assets_v1.py',ROOT/'tools/build_chapter02_enemy_sources.py'):locks[p.relative_to(ROOT.parent).as_posix()]=sha(p)
 assert all(sha(ROOT.parent/name)==pin for name,pin in locks.items())
 return {'schema':'ark-sim/chapter10-environment-source/v1','fixed_table_commit':plan['fixed_commit'],'source_locks':locks,'prefabs':prefabs,'native_monoscripts':assets.scripts,'bson_templates':bson,'stage_exact_map_data':{n:s['native_document']['mapData'] for n,s in plan['stages'].items()},'stage_tile_operands':{n:s['native_document']['mapData']['tiles'] for n,s in plan['stages'].items()},'routes_and_extra_routes':{n:{'routes':s['native_document']['routes'],'extra_routes':s['native_document'].get('extraRoutes')} for n,s in plan['stages'].items()},'source_version_policy':'Fixed56aee table/reference docs and local asset identities retained independently; client version alignment unverified','runtime_authored':False,'whole_stage_executed':False,'client_verified':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();v=build();raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode();OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:assert OUT.read_bytes()==raw
 else:assert not OUT.exists();OUT.write_bytes(raw)
 print(json.dumps({'sha':sha(OUT),'tiles':list(v['prefabs']),'runtime':False}))
