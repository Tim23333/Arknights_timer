"""Join exact C3 last-stage variants; retain source counts/runes/terrain."""
import argparse,hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PINS={
    'packages/campaign/chapter03_plans/source.plan.json':'d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6',
    'packages/campaign/chapter03_units/ordinary.reference_model.json':'daa790f1c89da896a34003197b71815643408fad44ad7fec2ceb4e45a59db0c7',
    'packages/campaign/chapter03_visibility/three_hidden_sensor.model.json':'32263bd62eae9f3c4d738a219f5e1a172ad87d2d16922e7290d70817497d7ceb',
    'packages/campaign/chapter03_models/skulsr.level1.reference.json':'c09cc02578055091f1ae465954ecfa484a6cafe21ab5b5b84f3c2deab8380092',
    'packages/campaign/chapter03_tiles/defup.reference_model.json':'79a0fc54e7509e1db5faafe477a3bce5a1c2aa4ab9e2af75018b93633ce77a59',
    'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
    'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'}


def build():
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario_v2 import compose,map_plan
    from tools.campaign_content_composition import compose_modules,reachable_content
    data={}
    for name,pin in PINS.items():
        raw=(ROOT/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Frozen C3 content drift:'+name)
        data[name]=json.loads(raw)
    plan=data['packages/campaign/chapter03_plans/source.plan.json'];stage=plan['stages']['level_main_03-08'];native=stage['native_document']
    modules=[('ordinary',data['packages/campaign/chapter03_units/ordinary.reference_model.json']),('hidden',data['packages/campaign/chapter03_visibility/three_hidden_sensor.model.json']),
        ('Bosslevel1',data['packages/campaign/chapter03_models/skulsr.level1.reference.json']),('defup200',data['packages/campaign/chapter03_tiles/defup.reference_model.json']),
        ('fixed12',data['packages/campaign/roster/fixed12.m26.reference_module.json'])]
    definitions,_=compose_modules(modules);units={}
    for definition in definitions.values():
        vid=definition.get('metadata',{}).get('native_variant_id',definition.get('metadata',{}).get('native_variant'))
        if definition['kind']=='entity' and vid:
            if vid in units:raise ValueError('Duplicate exact variant binding')
            units[vid]=definition['id']
    bindings={};rows=[]
    for vid in stage['variant_ids']:
        source=plan['variants'][vid];ref=source['native_reference']
        if vid not in units:raise ValueError('Missing exact C3 variant '+vid)
        if ref not in native['enemyDbRefs']:raise ValueError('Stage exact enemy ref mismatch')
        motion=source['native_enemy']['resolved']['motion'];bindings[ref['id']]={'unit':units[vid],'motion':motion}
        rows.append({'variant_id':vid,'native_reference':ref,'unit_definition':units[vid],'native_motion':motion})
    field={'tile_defup':{'type':'occupancy_buff_field','definition':'unit/ch3/field/defup','expected_blackboard':{'def':200.0}}}
    scene,controls=compose(native,'level_main_03-08',bindings,field);roster=data['packages/campaign/roster/fixed12.m26.reference_module.json']
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules']);scene['initialEntities']=[]
    move=definitions[scene['rules']['movement.speed']]
    if move['parameters']['multiplier']!=native['options']['moveMultiplier']:raise ValueError('Source moveMultiplier differs from current rule')
    modules += [('native_controls',{'controls':controls}),('spawn_policy',{'rules':[deepcopy(r) for r in data['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']['rules'] if r['id']=='rule/m7_spawn_rectangle']})]
    result,_=reachable_content(scene,modules,manifest_id='package/reference/level_main_03-08')
    result['manifest']['metadata'].update(source_locks=deepcopy(PINS),builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        required_runtime=implementation_digest(),variant_bindings=rows,full_stage_executed=False,actual_client_verified=False,pending_model_gaps=[],
        source_runtime_review_status='Independent generic/source modulepeer andstageconsumer reviews pending; executable model input only',
        feedback_pending=['Explicit actor getter/status mathdefaults','Reference50/serialized40 Bossphase correspondence','Fullstage native precision/sameframe userfeedback'],
        inherited_module_metadata={label:deepcopy(p.get('manifest',{}).get('metadata',{})) for label,p in modules})
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if not Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve()) or implementation_digest()!=args.expected_core:raise ValueError('Wrong selected C3 runtime')
    p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8');args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw);print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'defs':len(p['definitions']),'full_stage_executed':False}))
