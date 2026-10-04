"""Keep complete volcano/teleport tile prefabs and stage tile operands."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_chapter01_enemy_sources import NativeAssets,find_templates,bson_source
from tools.build_chapter02_enemy_sources import geometry_source
PLAN=ROOT/'packages/campaign/chapter04_plans/source.plan.json'
PIN='2b9a49412d64945eacca82282866b4c8b12eb11f5676dd831878a51ec01a9086'
OUT=ROOT/'packages/campaign/chapter04_environment/source.reference.json'


def build():
    import UnityPy
    if hashlib.sha256(PLAN.read_bytes()).hexdigest()!=PIN:raise ValueError('Source plan drift')
    plan=json.loads(PLAN.read_bytes());assets=NativeAssets();prefabs={};keys={'tile_volcano','tile_telin','tile_telout'};paths={key:[] for key in sorted(keys)}
    for path in (ROOT.parent/'data/battle/prefabs').glob('*tiles.ab_unpacked/CAB-*'):
        if path.name.endswith('.resS'):continue
        for obj in UnityPy.load(str(path)).objects:
            if obj.type.name=='GameObject' and obj.read().m_Name in keys:paths[obj.read().m_Name].append(path)
    for key,found in paths.items():
        if len(found)!=1:raise ValueError('Exact environment prefab missing/ambiguous:'+key)
        prefabs[key]=assets.closure(found[0],key)
        prefabs[key]['geometry_sources']=geometry_source(assets,prefabs[key])
    templates=bson_source(set().union(*(find_templates(p) for p in prefabs.values())))
    locks={str(PLAN.relative_to(ROOT.parent)):PIN}
    def collect(v):
        if isinstance(v,dict):
            if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):locks[v['path']]=v['sha256']
            for child in v.values():collect(child)
        elif isinstance(v,list):
            for child in v:collect(child)
    collect(prefabs);collect(templates);collect(assets.scripts)
    for p in (Path(__file__),ROOT/'tools/build_chapter01_enemy_sources.py',ROOT/'tools/build_chapter02_enemy_sources.py'):
        locks[p.relative_to(ROOT.parent).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    for name,pin in locks.items():
        if hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest()!=pin:raise ValueError('Source changed:'+name)
    return {'schema':'ark-sim/chapter04-environment-source/v1','source_locks':locks,'prefabs':prefabs,'native_monoscripts':assets.scripts,'bson_templates':templates,
        'stage_tile_operands':{name:[tile for tile in stage['native_document']['mapData']['tiles'] if tile['tileKey'] in keys] for name,stage in plan['stages'].items()},
        'source_route_transitions':{name:[{'route':index,'raw':stage['native_document']['routes'][index]} for index in stage['used_routes'] if any(c['type'] in ('DISAPPEAR','APPEAR_AT_POS') for c in stage['native_document']['routes'][index].get('checkpoints') or [])] for name,stage in plan['stages'].items()},
        'runtime_authored':False,'whole_stage_executed':False,'actual_client_verified':False}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Environment source bytes drift')
    else:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'prefabs':list(p['prefabs']),'source_locks':len(p['source_locks'])}))
