"""Source sensor tile rewrite on the frozen visibility module, explicit derivative."""
from copy import deepcopy
import argparse,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'packages/campaign/chapter03_visibility/lurker_sensor.model.json'
PIN='939ab55dea20624639a37d8a63c38cc015c2b8d9c214c0cdf6a3380f22821fe1'
PLAN=ROOT/'packages/campaign/chapter03_plans/source.plan.json'
PLAN_SHA='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6'
OUT=ROOT/'packages/campaign/chapter03_visibility/lurker_sensor.terrain.reference_model.json'


def build():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PIN or hashlib.sha256(PLAN.read_bytes()).hexdigest()!=PLAN_SHA:raise ValueError('Frozen sensor source drift')
    p=json.loads(PARENT.read_bytes());plan=json.loads(PLAN.read_bytes());native=plan['selected_native_prefabs']['trap_005_sensor']
    mode=next(r['raw'] for r in native['components'].values() if r['native_class']=='TrapMode')
    if mode['_keepCurrentPassableMask']!=0 or mode['_tileOptions']!={'buildableType':0,'passableMask':2,'overrideObstacleLikeMoveCost':0,'advancedBuildMask':0,'heightType':0} or mode['_rewriteTileHeight']!=1:
        raise ValueError('Sensor source tile rewrite needs a new adapter')
    unit=next(e for e in p['entities'] if e['id']=='unit/chapter03/trap_005_sensor')
    unit['components']['terrain_overlays']=[{'key':'native_sensor','priority':0,
        'values':{'buildableType':0,'passableMask':2,'obstacleLikeMoveCost':False,'physicalHeight':mode['_rewriteHeight']},'preserve':[]}]
    unit['metadata']['terrain_source']={'raw_mode':deepcopy(mode),'policy':'Native explicit terrain rewrite; actor category/blocking getters remain declared parent assumptions'}
    p['manifest']['id']+='/terrain_adapter';p['manifest']['metadata'].update(parent_source_module_sha256=PIN,
        terrain_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_plan_sha256=PLAN_SHA,
        native_sensor_predefine_bound=False,model_gaps=['Crate obstruction/destruction andsourcecard stagejoin remains separate'])
    return p


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Sensor terrain adapter drift')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'source_passable_mask':2}))
