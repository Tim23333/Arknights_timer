"""Source-validated parent eligibility before applying campaign base-life policy."""
import json
from pathlib import Path
from tools.chapter06_review.stage_converter_v7 import exact
from tools.chapter06_review.stage_converter_v6 import map_plan,route_ir
from tools.chapter06_review.source_locks_v1 import verify
ROOT=Path(__file__).resolve().parents[2]


def validate(parent):
    source=json.loads((ROOT/'packages/campaign/chapter06_plans/source.plan.json').read_bytes())
    s=parent['scenarioDraft'];meta=parent['manifest']['metadata'];key=s['metadata']['native_id']
    if key not in source['stages']:raise ValueError('Unknown source stage parent')
    native=source['stages'][key]['native_document'];verify(parent)
    fixed=json.loads((ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes())['manifest']['metadata']['roster']
    if not exact(s['roster'],fixed):raise ValueError('Parent must preserve exact fixed12 roster')
    options=native['options']
    if type(s['parameters']['deploy_capacity']) is not int or s['parameters']['deploy_capacity']!=options['characterLimit']:
        raise ValueError('Parent deployment limit differs from source')
    if not exact(s['resources']['life'],{'initial':options['maxLifePoint'],'capacity':options['maxLifePoint']}):
        raise ValueError('Parent native base-life differs')
    if not exact(s['resources']['dp'],{'initial':options['initialCost'],'capacity':options['maxCost'],
        'recovery_rate':1/options['costIncreaseTime'],'recovery':{'mode':'periodic','interval_seconds':options['costIncreaseTime']}}):
        raise ValueError('Parent DP differs from source')
    if not exact(meta['native_options'],options) or not exact(meta['native_predefines'],native['predefines']):
        raise ValueError('Parent native options/predefines source data differs')
    mp=map_plan(native)
    if not exact(s['map']['tiles'],mp['tiles']) or (s['map']['rows'],s['map']['cols'])!=(mp['rows'],mp['cols']):
        raise ValueError('Parent map differs from source')
    if not exact(s['seed'],native['randomSeed']):raise ValueError('Parent seed differs')
    initial=s.get('initialEntities',[])
    raw=[(bucket,r) for bucket in ('characterInsts','tokenInsts') for r in native['predefines'].get(bucket) or []]
    if len(initial)!=len(raw):raise ValueError('Parent predefined count differs')
    for item,(bucket,record) in zip(initial,raw):
        if not exact(item['parameters']['native_instance'],record) or item['parameters']['native_bucket']!=bucket:
            raise ValueError('Parent predefined raw instance differs')
        if item.get('active',True) is not (not record['hidden']):raise ValueError('Parent predefined active state differs')
        key=record['alias'] if record['alias'] is not None else record['inst']['characterKey']
        if record['hidden'] and item.get('registration_key')!=key:raise ValueError('Parent predefined registration differs')
        if not exact(item['position'],{'row':mp['rows']-1-record['position']['row'],'col':record['position']['col']}) or item['facing']!=record['direction'].lower():
            raise ValueError('Parent predefined placement differs')
    nw=native['waves'];sw=s['timeline']['waves']
    if len(nw)!=len(sw):raise ValueError('Parent wave count differs')
    for w,converted in zip(nw,sw):
        if len(w['fragments'])!=len(converted['fragments']):raise ValueError('Parent fragment count differs')
        for f,cf in zip(w['fragments'],converted['fragments']):
            if len(f['actions'])!=len(cf['actions']):raise ValueError('Parent action count differs')
            for a,ca in zip(f['actions'],cf['actions']):
                if not exact(a,ca['metadata']['native_action']):raise ValueError('Parent action raw source differs')
                if a['actionType']=='SPAWN':
                    route=route_ir(native['routes'][a['routeIndex']],mp['rows'])
                    if any(not exact(ca['spawn']['route'].get(k),v) for k,v in route.items()):raise ValueError('Parent route source differs')
    # Rebuild from independently pinned source modules, not from metadata
    # describing the supplied parent. This catches altered definitions,
    # timeline delays or effects even when their raw provenance is intact.
    from tools.chapter06_review.build_stage_v2 import build
    candidates=[]
    for name,pin in meta['source_locks'].items():
        path=Path(name)
        if path.is_absolute():
            module=json.loads(path.read_bytes())
            if module.get('manifest',{}).get('metadata',{}).get('native_variant_id') in source['stages'][s['metadata']['native_id']]['variant_ids']:
                candidates.append((path,pin))
    if len(candidates)!=1:raise ValueError('Parent requires one actual pinned boss module')
    expected=build(s['metadata']['native_id'],*candidates[0])
    if not exact(expected,parent):raise ValueError('Parent differs from exact reconstructed source-stage package')
    return {'native_id':s['metadata']['native_id'],'source_validated':True,'fixed12':12}
