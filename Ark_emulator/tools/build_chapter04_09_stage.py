"""Exact 4-9 seven-variant join; explicit policy and SHA-bound lasso module."""
import argparse,hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PINS={
 'packages/campaign/chapter04_plans/source.plan.json':'2b9a49412d64945eacca82282866b4c8b12eb11f5676dd831878a51ec01a9086',
 'packages/campaign/chapter04_units/ordinary.reference_model.json':'d53bcd485b0b67bf971fb39176fdb2abfa962e8c9055b6eb07ce643dbeff0038',
 'packages/campaign/chapter04_units/ranged/combat_guard.table.reference_model.json':'ff71a061f619069c7063bd1c7e13dfdf4d463b2bfbd5bd96767962c76510e0c2',
 'packages/campaign/chapter04_units/ranged/combat_guard.source_circle.reference_model.json':'d2a20696aed4a3c5d693500d4bd2e4c7311181b54f2912adb7bca17755f98bfd',
 'packages/campaign/chapter04_units/bslime.reference_model.json':'3aba5e741cd51df2e5e0bbf02055d4006e050aaeb6e9c258976b46ee4d9650d0',
 'packages/campaign/chapter04_environment/volcano.reference_module.json':'91e2f39a2e6c492bc0da90fcb65a21e0f951bdb3abdb3306d1d48d15193c1033',
 'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
 'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1'}


def load_bound(path,pin):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Frozen C4 content drift: '+str(path))
    return json.loads(raw)


def build(dmage_module,dmage_sha,demon_phase,demon_sha,range_policy):
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario_v2 import compose
    from tools.campaign_content_composition import compose_modules,reachable_content
    data={name:load_bound(ROOT/name,pin) for name,pin in PINS.items()}
    if demon_phase not in ('start','first_hit','finish') or range_policy not in ('table','source_circle'):
        raise ValueError('Explicit source model policies required')
    demon_path=ROOT/'packages/campaign/chapter04_units/demon_dynamic'/(demon_phase+'.model.json')
    demon=load_bound(demon_path,demon_sha);dmage=load_bound(dmage_module,dmage_sha)
    modules=[('ordinary',data['packages/campaign/chapter04_units/ordinary.reference_model.json']),
        ('demon_'+demon_phase,demon),('ranged_'+range_policy,data['packages/campaign/chapter04_units/ranged/combat_guard.'+range_policy+'.reference_model.json']),
        ('bslime',data['packages/campaign/chapter04_units/bslime.reference_model.json']),('dmage',dmage),
        ('volcano',data['packages/campaign/chapter04_environment/volcano.reference_module.json']),
        ('fixed12',data['packages/campaign/roster/fixed12.m26.reference_module.json'])]
    plan=data['packages/campaign/chapter04_plans/source.plan.json'];stage=plan['stages']['level_main_04-09'];native=stage['native_document']
    definitions,_=compose_modules(modules);units={}
    for definition in definitions.values():
        vid=definition.get('metadata',{}).get('native_variant_id',definition.get('metadata',{}).get('native_variant'))
        if definition['kind']=='entity' and vid:
            if vid in units:raise ValueError('Conflicting exact C4 variant binding: '+vid)
            units[vid]=definition['id']
    bindings={};rows=[]
    for vid in stage['variant_ids']:
        if vid not in units:raise ValueError('Missing exact required C4 variant: '+vid)
        ref=plan['variants'][vid]['native_reference'];motion=plan['variants'][vid]['native_enemy']['resolved']['motion']
        if ref not in native['enemyDbRefs']:raise ValueError('Actual stage enemy reference drift')
        bindings[ref['id']]={'unit':units[vid],'motion':motion}
        rows.append({'variant_id':vid,'native_reference':ref,'unit_definition':units[vid],'native_motion':motion})
    volcano=data['packages/campaign/chapter04_environment/volcano.reference_module.json']
    scene,controls=compose(native,'level_main_04-09',bindings,deepcopy(volcano['manifest']['metadata']['tile_profiles']))
    if controls:raise ValueError('4-9 actual source has no controls')
    roster=data['packages/campaign/roster/fixed12.m26.reference_module.json']
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    if definitions[scene['rules']['movement.speed']]['parameters']['multiplier']!=native['options']['moveMultiplier']:
        raise ValueError('Native movement multiplier not consumed')
    spawn=data['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']
    modules.append(('spawn_policy',{'rules':[deepcopy(r) for r in spawn['rules'] if r['id']=='rule/m7_spawn_rectangle']}))
    result,_=reachable_content(scene,modules,manifest_id='package/reference/level_main_04-09')
    locks={**PINS,str(demon_path.relative_to(ROOT)):demon_sha,str(Path(dmage_module).resolve()):dmage_sha}
    meta=result['manifest']['metadata'];meta.update(source_locks=locks,builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        required_runtime=implementation_digest(),variant_bindings=rows,source_births=stage['spawn_count'],
        model_policies={'demon_first_branch_consumption':demon_phase,'dcross_radius':range_policy},
        inherited_module_metadata={label:deepcopy(p.get('manifest',{}).get('metadata',{})) for label,p in modules},
        full_stage_executed=False,actual_client_verified=False,
        source_runtime_review_status='Executable exact stage join; independent consumer and full-stage receipts required')
    actual=sum(action.get('count',1) for wave in scene['timeline']['waves'] for fragment in wave['fragments'] for action in fragment['actions'] if action['kind']=='spawn')
    if actual!=49 or len(rows)!=7 or sum(t['tileKey']=='tile_volcano' for t in scene['map']['tiles'])!=8:
        raise ValueError('Exact 4-9 birth/variant/field accounting changed')
    Compiler().compile(result)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    ap.add_argument('--dmage-module',type=Path,required=True);ap.add_argument('--dmage-sha256',required=True)
    ap.add_argument('--demon-phase',choices=['start','first_hit','finish'],required=True);ap.add_argument('--demon-sha256',required=True)
    ap.add_argument('--range-policy',choices=['table','source_circle'],required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if Path(ark_sim.__file__).resolve().parent!=args.runtime_root.resolve()/'ark_sim' or implementation_digest()!=args.expected_core:
        raise ValueError('Wrong selected stage runtime')
    if args.output.exists():raise ValueError('Preserve existing authored stage package')
    p=build(args.dmage_module,args.dmage_sha256,args.demon_phase,args.demon_sha256,args.range_policy);raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'births':49,'variants':7,'fields':8,'full_stage_executed':False}))
