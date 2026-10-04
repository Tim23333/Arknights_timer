"""Join 3-7 with correct finite card timing, fee, path weight and connectivity."""
import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PINS={
 'packages/campaign/chapter03_plans/source.plan.json':'d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6',
 'validation/campaign/m57_obstacle_reentry/final.json':'b68fb5fb7e2de568295808388aba9d45484bc61782d0ab44e277fe860c7452e1',
 'validation/campaign/m59_area_primary/candidate_final.json':'09f9d50a164bc0eadf640c42167ebd492a9d215550f102af3d57c0ee361db5f8',
 'packages/campaign/chapter03_units/ordinary.reference_model.json':'daa790f1c89da896a34003197b71815643408fad44ad7fec2ceb4e45a59db0c7',
 'packages/campaign/chapter03_visibility/three_hidden_sensor.terrain.reference_model.json':'5f4e90a3aed8a48583d0a7aed620166f4726022e8b92d43e36c96b69fc81e5bf',
 'packages/campaign/chapter03_models/mortar.primary.reference.json':'632e455ac41ee3b2d95cd3d8d53fb8a6205445406d69df92b3f627763d3e7163',
 'packages/campaign/chapter03_traps/crate.reference_v3.model.json':'5a084db4d7d675867d8febf563b5e6e442c31422c5a184185fff5f5bcddbc8f9',
 'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'}


def build():
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario_v2 import compose,map_plan
    from tools.campaign_content_composition import compose_modules,reachable_content
    source={}
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Frozen C3 source changed:'+name)
        source[name]=json.loads(raw)
    plan=source['packages/campaign/chapter03_plans/source.plan.json'];stage=plan['stages']['level_main_03-07'];native=stage['native_document']
    ordinary=source['packages/campaign/chapter03_units/ordinary.reference_model.json']
    hidden=source['packages/campaign/chapter03_visibility/three_hidden_sensor.terrain.reference_model.json']
    mortar=source['packages/campaign/chapter03_models/mortar.primary.reference.json']
    crate=source['packages/campaign/chapter03_traps/crate.reference_v3.model.json']
    roster=source['packages/campaign/roster/fixed12.m26.reference_module.json']
    modules=[('ordinary',ordinary),('hidden_sensor_terrain',hidden),('mortar_reference_targeting',mortar),('crate_source',crate),('fixed12',roster)]
    definitions,_=compose_modules(modules)
    units={d['metadata']['native_variant_id']:d['id'] for d in definitions.values() if d['kind']=='entity' and d.get('metadata',{}).get('native_variant_id')}
    for row in hidden['manifest']['metadata'].get('variant_bindings',[]):
        units[row['variant_id']]=row['unit_definition']
    # Hidden entities bind native IDs in their own source metadata; the plan
    # still demands the exact three variants, never a name-only DB substitution.
    for vid in stage['variant_ids']:
        if vid in units:continue
        matches=[d for d in hidden['entities'] if d['id'].endswith(vid.split('/')[-1])]
        if len(matches)==1:units[vid]=matches[0]['id']
    units[mortar['manifest']['metadata']['native_variant']]=mortar['entities'][0]['id']
    bindings={};rows=[]
    for vid in stage['variant_ids']:
        if vid not in units:raise ValueError('Missing exact variant:'+vid)
        ref=plan['variants'][vid]['native_reference']
        if ref not in native['enemyDbRefs']:raise ValueError('Native enemy ref drift')
        motion=plan['variants'][vid]['native_enemy']['resolved']['motion']
        bindings[ref['id']]={'unit':units[vid],'motion':motion}
        rows.append({'variant_id':vid,'native_reference':ref,'unit_definition':units[vid],'native_motion':motion})
    mp=map_plan(native);sensor=native['predefines']['tokenInsts'][0];card=native['predefines']['tokenCards'][0]
    if sensor['inst']['characterKey']!='trap_005_sensor' or card['inst']['characterKey']!='trap_001_crate' or card['initialCnt']!=5:raise ValueError('Unexpected predefined source')
    predefines={'native_predefines':deepcopy(native['predefines']),
      'initial_entities':[{'definition':'unit/chapter03/trap_005_sensor','instanceAlias':'native_sensor',
          'position':{'row':mp['rows']-1-sensor['position']['row'],'col':sensor['position']['col']},
          'facing':sensor['direction'].lower(),'deployed':True,
          'parameters':{'native_bucket':'tokenInsts','native_instance':deepcopy(sensor)}}],
      'card_bindings':[{'native_bucket':'tokenCards','native_card':deepcopy(card),'definition':'unit/ch3/crate','stock_resource':'crate_cards'}],
      'resources':{'crate_cards':{'initial':5,'capacity':5}}}
    scene,controls=compose(native,'level_main_03-07',bindings,{},predefined_profile=predefines)
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster'])+['unit/ch3/crate']
    scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    from tools.build_reference_stage_scenario_v2 import route_ir
    from ark_sim.domains.spatial import project_cell
    protected=[]
    for index,native_route in enumerate(native['routes']):
        if native_route['motionMode'] not in ('WALK','FLY','E_NUM'):raise ValueError('Unknown native route motion')
        if native_route['motionMode']!='WALK':continue
        converted=route_ir(native_route,mp['rows'])
        start=project_cell(converted['startPosition']);end=project_cell(converted['endPosition'])
        protected.append({'id':'native_route/'+str(index),'start':{'row':start[0],'col':start[1]},'end':{'row':end[0],'col':end[1]}})
    if len(protected)!=40:raise ValueError('Expected all forty native ground routes, including unused future paths')
    scene['parameters']['deployment_routes']=protected
    scene['metadata']['protected_original_ground_route_indices']=[int(r['id'].rsplit('/',1)[1]) for r in protected]
    if definitions[scene['rules']['movement.speed']]['parameters']['multiplier']!=native['options']['moveMultiplier']:raise ValueError('Native speed multiplier mismatch')
    modules += [('native_controls',{'controls':controls}),('spawn_policy',{'rules':[deepcopy(r) for r in source['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']['rules'] if r['id']=='rule/m7_spawn_rectangle']})]
    result,_=reachable_content(scene,modules,manifest_id='package/reference/level_main_03-07')
    result['manifest']['metadata'].update(source_locks=deepcopy(PINS),builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       required_runtime=implementation_digest(),variant_bindings=rows,full_stage_executed=False,actual_client_verified=False,
       pending_model_gaps=[],
       feedback_pending=['Explicit planar projectile/source-validity/cell rounding policies','Base integer taunt versus live modifiers declared replacement','Actual game numerical calibration after delivery'],
       required_core_capabilities=['Callback-safe route obstacle stabilization, deployment-start cooldown, constant device fee and all-original-route connectivity','Pure include_primary area union with live eligibility'],
       status='New M68 source-bound executable join with all original ground routes protected; native Sensor/card and corrected obstacle/primary consumers; complete stage proof pending',
       inherited_module_metadata={label:deepcopy(p.get('manifest',{}).get('metadata',{})) for label,p in modules})
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()) or implementation_digest()!=args.expected_core:raise ValueError('Wrong selected runtime')
    p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8');args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'definitions':len(p['definitions']),'accepted':False}))
