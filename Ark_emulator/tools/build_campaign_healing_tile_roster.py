"""New source-bound roster adapter; original fixed12 module stays frozen."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
SOURCE_SHA='fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04'
OUT=ROOT/'packages/campaign/roster/fixed12.healing_tile.reference_module.json'


def build():
    from tools.campaign_tile_recovery_adapter import adapt_unit
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('Frozen roster source drift')
    p=json.loads(raw);adapted=[]
    for index,definition in enumerate(p['definitions']):
        if definition['kind']=='entity' and 'player' in definition.get('tags',[]):
            p['definitions'][index]=adapt_unit(definition,{'native_tile':'tile_healing','source_ratio':.03,
                'source_module':'packages/campaign/chapter02_tiles/buffs.motion_state.partial.json'})
            adapted.append(definition['id'])
    if len(adapted)!=15:raise ValueError('Expected actual twelve operators plus three owned units')
    p['manifest']['id']+='/healing_tile_driver'
    p['manifest']['metadata'].update(parent_roster_sha256=SOURCE_SHA,healing_driver_actors=adapted,
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        adapter_sha256=hashlib.sha256((ROOT/'tools/campaign_tile_recovery_adapter.py').read_bytes()).hexdigest(),
        required_external_rule='rule/ch2/tile_hp_ratio_recovery',source_hp_capacity_and_selected_abilities_unchanged=True)
    return p


if __name__=='__main__':
    sys.path.insert(0,str(ROOT));ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Healing driver roster changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'adapted_actor_count':15}))
