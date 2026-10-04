"""Compose exact reviewed five-enemy module; previous exploratory input frozen."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PINS={
    'packages/campaign/native_reference/level_main_02-09.json':'273821d71589c227e9fd101ca62c1989fff27a0d18ee46ad7537a2e02ceabdcf',
    'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1',
    'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
    'packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json':'4d9d07839243f1d2a7d7852f8952415f6971496473483765148a2def9ec10306',
    'validation/campaign/chapter02_five/m44_final.json':'39fb7a365decb9b4640a4b060ab9e978374c512b5bf43c2028b6ae097d70c159',
    'packages/campaign/chapter02_tiles/fields.lossless_request.model.json':'48c31d15e06bacdfa3d3c157e9ed9b6e17bbb52659880593c22d9047e4f8dfec',
    'packages/campaign/chapter02_tiles/buffs.lossless_request.model.json':'2dc2d9afe003d35d25f5e1d2897d34d5996d3c83291595c8cc97e76230fade46',
    'packages/campaign/chapter02_tiles/m41.hole.profile.json':'56295b4c0388e44230992bcaeb1b70d21b36b47beb71b4e2d17fea42074349d8'}


def build():
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario import compose,map_plan
    from tools.build_chapter02_tile_fields import profiles
    from tools.campaign_content_composition import reachable_content
    inputs={}
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Reviewed stage source drift: '+name)
        inputs[name]=json.loads(raw)
    enemies=inputs['packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json']
    review=inputs['validation/campaign/chapter02_five/m44_final.json']
    if review.get('passed') is not True or review.get('source_start')!=review.get('source_end') or review.get('core_start')!=review.get('core_end'):
        raise ValueError('Enemy review lacks stable execution/source identity')
    source_path='packages/campaign/chapter02_units/main_02-09.enemies.reference_module.json'
    if review['source_start'].get(str((ROOT/source_path).resolve()))!=PINS[source_path]:raise ValueError('Enemy review does not bind actual enemy input')
    native=inputs['packages/campaign/native_reference/level_main_02-09.json'];rows=enemies['manifest']['metadata']['variant_bindings']
    if {r['id']:r for r in native['enemyDbRefs']}!={r['native_reference']['id']:r['native_reference'] for r in rows}:
        raise ValueError('Exact five variants differ from actual enemyDbRefs')
    bindings={r['native_reference']['id']:{'unit':r['unit_definition'],'motion':r['native_motion']} for r in rows}
    hole=inputs['packages/campaign/chapter02_tiles/m41.hole.profile.json']
    scene,controls=compose(native,'level_main_02-09',bindings,{**profiles(map_plan(native)),**hole['tile_mechanics']})
    roster=inputs['packages/campaign/roster/fixed12.m26.reference_module.json']
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules']);scene['initialEntities']=[]
    movement=next(d for d in roster['definitions'] if d['id']==scene['rules']['movement.speed'])
    if movement['parameters'].get('multiplier')!=native['options']['moveMultiplier']:
        raise ValueError('Scene moveMultiplier requires an explicit source-backed movement rule')
    modules=[('fixed12',roster),('reviewed_five_enemies',enemies),
        ('field_lossless',inputs['packages/campaign/chapter02_tiles/fields.lossless_request.model.json']),
        ('numeric_lossless',inputs['packages/campaign/chapter02_tiles/buffs.lossless_request.model.json']),
        ('source_hole',{'rules':hole['rules']}),('native_control',{'controls':controls}),
        ('generic_spawn',{'rules':[deepcopy(r) for r in inputs['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']['rules'] if r['id']=='rule/m7_spawn_rectangle']})]
    replacements={}
    definitions={d['id']:d for d in enemies['definitions']}
    for row in rows:
        unit=deepcopy(definitions[row['unit_definition']])
        motion=1 if row['native_motion']=='WALK' else 2
        original=unit['components'].get('selection_state',{})
        unit['components']['selection_state']={'side':1,'motion':motion,'category':1,'profession':0,'unit_type':2,
            'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False,
            'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[],**deepcopy(original)}
        if unit['components']['selection_state']['motion']!=motion:raise ValueError('Typed selection motion conflicts with actual variant')
        unit['metadata']['typed_state_stage_adapter']={'variant_id':row['variant_id'],'source_motion':row['native_motion'],
            'source_literal_motion_mask':motion,'unknown_getter_policy':'Explicit enemy side1/category1/unit-type2 and standard inactive status defaults; live Buff flags project independently.'}
        replacements[unit['id']]={'definition':unit,'reason':'Gazebo hook reads actual typed entity state; selector default projection alone does not populate this field.',
            'source':{'module_sha256':PINS[source_path],'exact_variant_id':row['variant_id'],'motion':row['native_motion']}}
    result,_=reachable_content(scene,modules,replacements,manifest_id='package/reference/level_main_02-09/source_closed_v2')
    result['manifest']['metadata'].update(source_locks=deepcopy(PINS),required_runtime=implementation_digest(),
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        helpers={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('tools/build_reference_stage_scenario.py','tools/build_chapter02_tile_fields.py','tools/campaign_content_composition.py')},
        inherited_module_metadata={label:deepcopy(module.get('manifest',{}).get('metadata',{})) for label,module in modules},
        pending_model_gaps=[],actual_client_verified=False,full_stage_executed=False,
        status='reference_source_bound_input; known M42 reentry issue requires new reviewed runtime before final acceptance')
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()) or implementation_digest()!=args.expected_core:raise ValueError('Wrong selected runtime')
    result=build();raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8');args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'author_definitions':len(result['definitions']),'stage_execution_proved':False}))
