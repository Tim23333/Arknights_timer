"""Explicit typed motion-state adapter for source FLY_ONLY tile damage."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_chapter02_tile_buff_models import build as original


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    p=deepcopy(original());parent=ROOT/'packages/campaign/chapter02_tiles/buffs.partial.json'
    if sha(parent)!='0101470fa4e3d9426f9e5b10a2f62033b80dfbcf9f9c6458da68ba800b02a697':raise ValueError('Frozen tile operand module changed')
    gazebo=next(b for b in p['buffs'] if b['id']=='buff/ch2/gazebo_member')
    gazebo['damage_hooks'][0]['condition']='inputs.target.components.selection_state.motion in [2, 3]'
    gazebo['metadata']['target_motion_adapter']='explicit typed selection_state.motion mask contains FLY2; missing state rejects, no identifier/tag fallback'
    p['manifest']['id']+='/typed_motion';p['manifest']['metadata'].update(parent_sha256=sha(parent),motion_builder_sha256=sha(__file__),
        required_actor_state=['selection_state.motion'],typed_motion_encoding={'WALK':1,'FLY':2,'ALL':3},
        tag_adapter_removed='chapter02 source actors use fly while earlier synthetic probes used flying; type state avoids tag spelling dependence',
        native_motion_getter_verified=False)
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();p=build()
    out=ROOT/'packages/campaign/chapter02_tiles/buffs.motion_state.partial.json';raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if out.read_bytes()!=raw:raise ValueError('Typed motion tile module changed')
    else:out.write_bytes(raw)
    print(json.dumps({'sha256':sha(out),'native_verified':False,'scope':'typed declared motion, source FLY_ONLY operands'}))
