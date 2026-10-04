"""Consume the native DEFAULT entity-category mask via a generic field predicate."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter01_devices/emp.partial.json'
PIN='98f668b2f130a4e47e27151d92cbf3d1ad59789e147ec4adc80a98a14679e854'
OUTPUT=ROOT/'packages/campaign/chapter01_devices/emp.category.json'


def build():
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen EMP source slice changed')
    p=json.loads(raw);native=json.loads((SOURCE.parent/'emp.source.json').read_bytes())
    selector=next(c['raw'] for c in native['skill_prefab']['components'].values() if c['native_class']=='AdvancedSelector')
    if selector['_targetCategory']!=1:raise ValueError('Native EMP category mask changed')
    p['selectors'][0]['filters'].append({'field':{'scope':'definition','path':['metadata','native_category'],'bits_any':1,'default':1}})
    p['manifest']['metadata']['category_profile']={'source_target_category_mask':1,
        'entity_category_declaration':{'NONE':0,'DEFAULT':1,'TRAP_OR_ITEM':2,'OBSTACLE':4},
        'ordinary_entity_missing_category_default':1,'mask_test':'integer category & source mask !=0',
        'bool_float_or_unknown_string_not_coerced':True,'source_slice_sha256':PIN,
        'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'stage_import_must_preserve_native_category':True}
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes()!=raw:raise ValueError('EMP category wrapper changed')
    else:OUTPUT.write_bytes(raw)
    print(json.dumps({'output':str(OUTPUT),'sha256':hashlib.sha256(raw).hexdigest(),'formal_approval':False}))
