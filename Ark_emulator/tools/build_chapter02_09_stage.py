"""Assemble exact 2-9 variants, twelve-person module and reviewed terrain."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PINS={
    'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1',
    'packages/campaign/native_reference/level_main_02-09.json':'273821d71589c227e9fd101ca62c1989fff27a0d18ee46ad7537a2e02ceabdcf',
    'packages/campaign/chapter02_sources/native.reference.json':'97447895b3edc69f0f60113ea96bc240c25c0fe980897614e93a94dd75e0d492',
    'packages/campaign/chapter02_units/main_02-09.enemy_binding.plan.json':'346a6bfc20add835d70d65ea18b09310d8542578be0693a8228891a7cbcebd9d',
    'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
    'packages/campaign/chapter02_behavior/models.partial.json':'bda5488a79f44e195e23631f579d313de833f356f1decec6d6abd726800f9bc8',
    'packages/campaign/chapter02_units/airdrp.birth_contact.model.json':'ee1b526bafdd61f3c924d9f58bc7c9c109e0db300ff2c72a84455989744bb44e',
    'packages/campaign/chapter02_tiles/fields.lossless_request.model.json':'48c31d15e06bacdfa3d3c157e9ed9b6e17bbb52659880593c22d9047e4f8dfec',
    'packages/campaign/chapter02_tiles/buffs.lossless_request.model.json':'2dc2d9afe003d35d25f5e1d2897d34d5996d3c83291595c8cc97e76230fade46',
    'packages/campaign/chapter02_tiles/m41.hole.profile.json':'56295b4c0388e44230992bcaeb1b70d21b36b47beb71b4e2d17fea42074349d8'}


def load_pinned(path,pin):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Frozen stage composition source drift: '+str(path))
    return json.loads(raw)


def build(defdrn_package,defdrn_sha256,review_report,review_sha256):
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario import compose,map_plan
    from tools.build_chapter02_tile_fields import profiles
    from tools.campaign_content_composition import reachable_content

    inputs={name:load_pinned(ROOT/name,pin) for name,pin in PINS.items()}
    defdrn=load_pinned(defdrn_package,defdrn_sha256);review=load_pinned(review_report,review_sha256)
    if review.get('passed') is not True:raise ValueError('Defdrn/removal review has not passed')
    guarded=review.get('source_start',{})
    if guarded.get(str(Path(defdrn_package).resolve()))!=defdrn_sha256 or guarded!=review.get('source_end'):
        raise ValueError('Defdrn review does not bind actual module bytes before and after execution')
    if review.get('core_start')!=review.get('core_end') or not review.get('core_start'):
        raise ValueError('Defdrn review does not bind a stable runtime identity')
    native=inputs['packages/campaign/native_reference/level_main_02-09.json']
    plan=inputs['packages/campaign/chapter02_units/main_02-09.enemy_binding.plan.json']
    native_refs={row['id']:row for row in native['enemyDbRefs']}
    bindings={}
    for row in plan['five_variant_bindings']:
        if native_refs.get(row['native_reference']['id'])!=row['native_reference']:
            raise ValueError('Exact native enemy variant join mismatch')
        bindings[row['native_reference']['id']]={'unit':row['unit_definition'],'motion':row['native_motion']}
    hole=inputs['packages/campaign/chapter02_tiles/m41.hole.profile.json']
    tile_profiles={**profiles(map_plan(native)),**deepcopy(hole['tile_mechanics'])}
    scene,controls=compose(native,'level_main_02-09',bindings,tile_profiles)
    roster=inputs['packages/campaign/roster/fixed12.m26.reference_module.json']
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster'])
    scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    scene['initialEntities']=[]
    base=inputs['packages/campaign/chapter02_behavior/models.partial.json']
    replacements={}
    for collection in ('entities','selectors','buffs','rules','abilities','behaviors'):
        old={r['id']:r for r in base.get(collection,[])}
        for row in defdrn.get(collection,[]):
            if row['id'] in old:
                replacements[row['id']]={'definition':deepcopy(row),'reason':'Source-bound live silence/qualification defdrn model replaces earlier numerical prototype',
                    'source':{'path':str(defdrn_package),'sha256':defdrn_sha256,'review_sha256':review_sha256}}
    new_only=deepcopy(defdrn)
    for collection in ('entities','selectors','buffs','rules','abilities','behaviors'):
        new_only[collection]=[r for r in new_only.get(collection,[]) if r['id'] not in replacements]
    modules=[('fixed12',roster),('chapter02_initial_enemy_models',base),('defdrn_reviewed_model',new_only),
        ('airdrop_birth_contact',inputs['packages/campaign/chapter02_units/airdrp.birth_contact.model.json']),
        ('tile_fields_lossless',inputs['packages/campaign/chapter02_tiles/fields.lossless_request.model.json']),
        ('tile_numeric_lossless',inputs['packages/campaign/chapter02_tiles/buffs.lossless_request.model.json']),
        ('ground_contact',{'rules':hole['rules']}),('native_info_controls',{'controls':controls}),
        ('reference_generic_spawn_policy',{'rules':[deepcopy(r) for r in inputs['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']['rules']
            if r['id']=='rule/m7_spawn_rectangle']})]
    # Exact source mass and explicit state for the non-attacking drone, whose
    # prototype had neither; field hooks read the typed motion state.
    for native_id in ('enemy_1005_yokai','enemy_1005_yokai_2'):
        uid='unit/chapter02/'+native_id;unit=deepcopy(next(r for r in base['entities'] if r['id']==uid))
        unit['components']['selection_state']={'side':1,'motion':2,'category':1,'profession':0,'unit_type':2,
            'target_free':False,'ally_target_free':False,'heal_free':False,'camouflage':False,'can_select_camouflage':False,
            'abnormal_flags':[],'abnormal_combos':[],'target_free_flags':[],'target_free_combos':[]}
        unit['components']['attributes']['base']['mass_level']=0
        binding=next(row for row in plan['five_variant_bindings'] if row['native_reference']['id']==native_id)
        replacements[uid]={'definition':unit,'reason':'Actual variant defined mass0 and source motion FLY2; unknown side/status getters use explicit standard model.',
            'source':{'variant':binding['variant_id'],'binding_sha256':PINS['packages/campaign/chapter02_units/main_02-09.enemy_binding.plan.json']}}
    package,composition=reachable_content(scene,modules,replacements,manifest_id='package/reference/level_main_02-09')
    meta=package['manifest']['metadata'];meta.update(required_runtime=implementation_digest(),source_locks={**PINS,str(defdrn_package):defdrn_sha256,str(review_report):review_sha256},
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),composition_helpers={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('tools/build_reference_stage_scenario.py','tools/build_chapter02_tile_fields.py','tools/campaign_content_composition.py')},
        inherited_module_metadata={label:deepcopy(module.get('manifest',{}).get('metadata',{})) for label,module in modules},
        status='reference_source_bound_full_stage_input_not_execution_receipt',
        pending_model_gaps=[],actual_client_verified=False,feedback_pending=['Inherited definition-level source/model policies',
            'Standard NORMAL1 rune mask policy; native NONE0 application feedback pending',
            'Declared logical UI acknowledgement and native wall-clock pause','Tile field/collision/numerical rounding source interpretation'])
    return package


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    for name in ('defdrn-package','review-report','output'):ap.add_argument('--'+name,type=Path,required=True)
    for name in ('defdrn-sha256','review-sha256'):ap.add_argument('--'+name,required=True)
    args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()) or implementation_digest()!=args.expected_core:
        raise ValueError('Wrong explicitly selected stage runtime')
    p=build(args.defdrn_package,args.defdrn_sha256,args.review_report,args.review_sha256)
    raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8');args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'definitions':len(p['definitions']),'actual_stage_executed':False}))
