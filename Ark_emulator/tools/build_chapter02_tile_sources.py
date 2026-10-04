"""Offline exact tile prefab, blackboard and template dependencies for chapter2."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_chapter01_enemy_sources import NativeAssets,identity,find_templates,bson_source


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    asset_paths=list((ROOT.parent/'data/battle/prefabs/[uc]tiles.ab_unpacked').glob('CAB-*'))
    if len(asset_paths)!=1:raise ValueError('Tile prefab CAB ambiguous')
    assets=NativeAssets();prefabs={key:assets.closure(asset_paths[0],key) for key in ('tile_healing','tile_gazebo','tile_hole')}
    templates=bson_source(set().union(*(find_templates(v) for v in prefabs.values())))
    stages={};source_locks={str(Path(__file__).relative_to(ROOT)):sha(__file__)}
    for stage in ('02-09','02-10'):
        path=ROOT/f'packages/campaign/native_reference/level_main_{stage}.json';raw=path.read_bytes();data=json.loads(raw)
        source_locks[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest();m=data['mapData'];grid=m['map'];cells=[]
        for native_row,row in enumerate(grid):
            for col,index in enumerate(row):
                tile=m['tiles'][index]
                if tile['tileKey'] in prefabs:
                    cells.append({'native_map_row':native_row,'col':col,'tile_index':index,'raw_tile':deepcopy(tile)})
        stages[stage]={'level_source':identity(path),'native_map':deepcopy(m),'selected_special_cells':cells,
            'coordinate_policy':'native map row indices only; importer row flip/projected occupancy must be explicitly bound',
            'options':deepcopy(data['options'])}
    for p in prefabs.values():source_locks['../'+p['source']['path']]=p['source']['sha256']
    for script in assets.scripts.values():source_locks['../'+script['source']['path']]=script['source']['sha256']
    source_locks['../'+templates['source']['path']]=templates['source']['sha256']
    dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';raw_dump=dump.read_bytes();source_locks['../Ark_data/Il2CppDumper_current/dump.cs']=hashlib.sha256(raw_dump).hexdigest()
    text=raw_dump.decode('utf-8-sig');declarations={}
    for label in ('public class BuffTile :','public class DynamicBuffTile :','public class HoleTile :'):
        start=text.index(label);end=text.index('\n// Namespace:',start)
        declarations[label]={'start_line':text[:start].count('\n')+1,'raw':text[start:end],
            'method_body_status':'empty dump signatures, not native algorithm'}
    refs=[]
    for key,prefab in prefabs.items():
        roots=[(pid,c) for pid,c in prefab['components'].items() if c['gameobject_path_id']==prefab['root_gameobject_path_id']]
        refs.extend({'tile_key':key,'component_path_id':int(pid),'native_class':c['native_class'],'raw':deepcopy(c['raw'])} for pid,c in roots)
    return {'schema':'ark-sim/chapter02-tile-source/v1','status':'exact_source_dependencies_client_pending','source_locks':source_locks,
        'prefabs':prefabs,'scripts':assets.scripts,'templates':templates,'stages':stages,'root_components':refs,'dump_declarations':declarations,
        'known_requirements':['hole movement/lethal entry and flight distinction','gazebo ATKscale1.7 and attackSpeed−20 from native blackboard',
            'healing MaxHP ratio.03 nativeblackboard, clear-on-leave/sourceTargetOptions',
            'BSONtemplate attribute binding/target selection/callback and status-free semantics'],
        'pending_native_algorithms':['BuffTile target/enter/leave/reborn/category callbacks','HoleTile entry and motion-changed behavior',
            'Buff formula blackboard scaling/precision and tick ordering','Tile-to-map row/continuous-body occupancy semantics'],
        'actual_game_accuracy_verified':False,'formal_approved':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();value=build()
    out=ROOT/'packages/campaign/chapter02_tiles/source.reference.json';raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if out.read_bytes()!=raw:raise ValueError('Tile source output drift')
    else:out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw)
    print(json.dumps({'tile_roots':len(value['root_components']),'locks':len(value['source_locks']),'sha256':sha(out),'native_accuracy':False}))
