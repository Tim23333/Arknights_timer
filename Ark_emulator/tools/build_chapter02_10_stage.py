"""Compose 2-10 only from an actually reviewed exact enemy input module."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STATIC={
    'packages/campaign/native_reference/level_main_02-10.json':'27c0f11c1fda9a6ed66d85e1a3078ebe6a038f8aeb08396d01dfab3db56c5dad',
    'packages/campaign/roster/fixed12.healing_tile.reference_module.json':'e1e4f053f5c0e45e4aa3d3e54be7e923b40ba76ad9c54c6f351c605257da1f31',
    'packages/campaign/chapter02_tiles/fields.lossless_request.model.json':'48c31d15e06bacdfa3d3c157e9ed9b6e17bbb52659880593c22d9047e4f8dfec',
    'packages/campaign/chapter02_tiles/buffs.lossless_request.model.json':'2dc2d9afe003d35d25f5e1d2897d34d5996d3c83291595c8cc97e76230fade46',
    'packages/campaign/chapter02_stage_models/controls.reference_model.json':'c901279e9b3366faa8731d88a56f531733aed81ebfb32987937d926f108a2e5a',
    'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'}


def load_pinned(path,pin):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Source byte drift: '+str(path))
    return json.loads(raw)


def build(enemy_path,enemy_sha,review_path,review_sha):
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario import compose,map_plan
    from tools.build_chapter02_tile_fields import profiles
    from tools.campaign_content_composition import reachable_content
    sources={name:load_pinned(ROOT/name,pin) for name,pin in STATIC.items()}
    enemies=load_pinned(enemy_path,enemy_sha);review=load_pinned(review_path,review_sha)
    if review.get('passed') is not True or review.get('source_start')!=review.get('source_end') or review.get('core_start')!=review.get('core_end'):
        raise ValueError('Enemy review is not a stable successful execution')
    if review['source_start'].get(str(Path(enemy_path).resolve()))!=enemy_sha:raise ValueError('Review does not bind actual enemy module')
    native=sources['packages/campaign/native_reference/level_main_02-10.json'];rows=enemies['manifest']['metadata']['variant_bindings']
    if {r['id']:r for r in native['enemyDbRefs']}!={r['native_reference']['id']:r['native_reference'] for r in rows}:raise ValueError('Exact12variant enemy join mismatch')
    if len(rows)!=12 or sum(r['spawn_count'] for r in rows)!=36:raise ValueError('Native12variants/36births required')
    bindings={r['native_reference']['id']:{'unit':r['unit_definition'],'motion':r['native_motion']} for r in rows}
    stories=sources['packages/campaign/chapter02_stage_models/controls.reference_model.json']
    scene,controls=compose(native,'level_main_02-10',bindings,profiles(map_plan(native)),
        story_controls={c['metadata']['native_story_key']:c for c in stories['controls']})
    roster=sources['packages/campaign/roster/fixed12.healing_tile.reference_module.json']
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules']);scene['initialEntities']=[]
    move=next(d for d in roster['definitions'] if d['id']==scene['rules']['movement.speed'])
    if move['parameters']['multiplier']!=native['options']['moveMultiplier']:raise ValueError('Native moveMultiplier differs from selected rule')
    for unit in enemies['definitions']:
        if unit['kind']=='entity' and 'enemy' in unit.get('tags',[]) and unit['components'].get('selection_state',{}).get('motion') not in (1,2):
            raise ValueError('Required typed enemy motion missing: '+unit['id'])
    modules=[('fixed12_healing_driver',roster),('source_closed12',enemies),
        ('fields',sources['packages/campaign/chapter02_tiles/fields.lossless_request.model.json']),
        ('numerics',sources['packages/campaign/chapter02_tiles/buffs.lossless_request.model.json']),
        ('native_controls',{'controls':controls}),('generic_spawn',{'rules':[deepcopy(r) for r in sources['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']['rules'] if r['id']=='rule/m7_spawn_rectangle']})]
    result,_=reachable_content(scene,modules,manifest_id='package/reference/level_main_02-10')
    result['manifest']['metadata'].update(source_locks={**STATIC,str(enemy_path):enemy_sha,str(review_path):review_sha},
        required_runtime=implementation_digest(),builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inherited_module_metadata={label:deepcopy(m.get('manifest',{}).get('metadata',{})) for label,m in modules},
        pending_model_gaps=[],full_stage_executed=False,actual_client_verified=False,
        status='source-bound executable reference input; complete run and independent source review pending')
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    for name in ('enemy-package','review-report','output'):ap.add_argument('--'+name,type=Path,required=True)
    for name in ('enemy-sha256','review-sha256'):ap.add_argument('--'+name,required=True)
    args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()) or implementation_digest()!=args.expected_core:raise ValueError('Wrong selected runtime')
    p=build(args.enemy_package,args.enemy_sha256,args.review_report,args.review_sha256);raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw);print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'defs':len(p['definitions']),'full_stage_executed':False}))
