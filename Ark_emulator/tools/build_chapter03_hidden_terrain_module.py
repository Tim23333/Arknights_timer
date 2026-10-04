"""Compose frozen three hidden units and source sensor tile adapter."""
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter03_visibility/three_hidden_sensor.model.json'
PARENT_SHA='32263bd62eae9f3c4d738a219f5e1a172ad87d2d16922e7290d70817497d7ceb'
ADAPTER=ROOT/'packages/campaign/chapter03_visibility/lurker_sensor.terrain.reference_model.json'
ADAPTER_SHA='08ff611c2d568263bda11087dc4bdd1c0bda8839f3efda710a4ea37f0ae26654'
OUT=ROOT/'packages/campaign/chapter03_visibility/three_hidden_sensor.terrain.reference_model.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PARENT_SHA or hashlib.sha256(ADAPTER.read_bytes()).hexdigest()!=ADAPTER_SHA:raise ValueError('Frozen hidden/terrain source changed')
    p=json.loads(PARENT.read_bytes());adapter=json.loads(ADAPTER.read_bytes());source=next(e for e in adapter['entities'] if e['id']=='unit/chapter03/trap_005_sensor');sensor=next(e for e in p['entities'] if e['id']==source['id'])
    sensor['components']['terrain_overlays']=source['components']['terrain_overlays'];sensor['metadata']['terrain_source']=source['metadata']['terrain_source']
    p['manifest']['id']+='/sensor_terrain';p['manifest']['metadata'].update(three_hidden_parent_sha256=PARENT_SHA,terrain_adapter_parent_sha256=ADAPTER_SHA,native_sensor_predefine_bound=False)
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Hidden terrain derived output changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'hidden_units':3}))
