"""Preserve every custom pipeline operand in source FLY-only field scaling."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD_NUMERIC=ROOT/'packages/campaign/chapter02_tiles/buffs.motion_state.partial.json'
OLD_FIELDS=ROOT/'packages/campaign/chapter02_tiles/fields.reference_model.json'
OUT=ROOT/'packages/campaign/chapter02_tiles'
PINS={OLD_NUMERIC:'25d8b684b3ed96f4274feeaab65a455db07550ab5f06575cdf7b972f19b62c10',
      OLD_FIELDS:'b35e21da93109e4d32b17cc413dcf5d2744d36b5bbf90c251171cb136e45f167'}


def build():
    for path,pin in PINS.items():
        if hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise ValueError('Frozen tile parent drift')
    numeric=json.loads(OLD_NUMERIC.read_bytes());fields=json.loads(OLD_FIELDS.read_bytes())
    rule=next(r for r in numeric['rules'] if r['id']=='rule/ch2/gazebo_flying_scale')
    rule['implementation']={'type':'provider','provider':'model.damage.request_field_transform'}
    rule['parameters']={'field':'scale','factor':1.7,'default':1}
    rule['metadata']={'preserve_request':'All fields retained; custom pipeline may intentionally ignore scale, e.g. Weedy distance true damage.',
        'source_numeric_factor':1.7,'native_true_damage_hook_behavior_pending':True}
    for module in [numeric,fields]:
        module['manifest']['id']+='/lossless_request'
        module['manifest']['metadata'].update(request_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            request_parent_locks={str(path.relative_to(ROOT)).replace('\\','/'):pin for path,pin in PINS.items()},
            required_core_provider='model.damage.request_field_transform')
    return {'buffs.lossless_request.model.json':numeric,'fields.lossless_request.model.json':fields}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    results={}
    for name,value in build().items():
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8');path=OUT/name
        if args.check:
            if path.read_bytes()!=raw:raise ValueError('Lossless tile model drift')
        else:path.write_bytes(raw)
        results[name]=hashlib.sha256(raw).hexdigest()
    print(json.dumps(results))
