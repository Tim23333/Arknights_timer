"""Exact chapter5 joins require every native variant and real ballista profiles.

Native life stays unchanged here; the separate standard goal overlay changes
only base life. Branch source is validated before converting a new IR program.
"""
import argparse,hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PINS={
    'tools/build_reference_stage_scenario_v4.py':'4882dba0a90712a84849d5068f2789c04b6fc213a0ecbd9b80a130f264153176',
    'packages/campaign/chapter05_plans/source.plan.json':'c33c5a199fce73ef7b7524e0d29e59eeca6eb69a7f2ebd7d8c253634b050bee6',
    'packages/campaign/chapter05_units/ordinary.reference_model.json':'dda894f38a083eb7f5edb54e051498e68dfd592cf8e4773ad9e582007688919b',
    'packages/campaign/chapter05_units/regenerating/model.json':'6c4cb6a264b3f66a7d084070b67ea0bf25020d2fe2fe5a1d46c61a4a46e5e01b',
    'packages/campaign/chapter05_units/special/model.selection_settle.reference.json':'fa314fcf5e46ddcef792ced3f1f7f86cc1586d7f74e5915af305f270dff55b8d',
    'packages/campaign/chapter05_boss/mephi/model.json':'c96480241c8bff878e0017525606dbdede7a42d2d06a16b49893d8c0a4ce3fe1',
    'packages/campaign/roster/fixed12.m26.reference_module.json':'fd48b0cc67a6b96457b6d7df69397493b3914d65676c554a92b90193374c2c04',
    'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json':'a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1',
    'packages/campaign/chapter05_boss/faust/branch.reference.json':'2447fa97a705ab7fa168fbef6dfa39ed5c2d2c9c1d6f2fb1864d56804bb55c66'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(path,pin):
    if sha(path)!=pin:raise ValueError('Frozen content drift '+str(path))
    return json.loads(Path(path).read_bytes())
def build(stage_id,ballista_path,ballista_sha,faust_path,faust_sha):
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.build_reference_stage_scenario_v4 import compose
    from tools.campaign_content_composition import compose_modules,reachable_content
    if stage_id not in ('level_main_05-09','level_main_05-10'):raise ValueError('Unsupported exact chapter5 stage')
    data={path:bound(ROOT/path,pin) for path,pin in PINS.items() if path.endswith('.json')}
    if sha(ROOT/'tools/build_reference_stage_scenario_v4.py')!=PINS['tools/build_reference_stage_scenario_v4.py']:raise ValueError('Selected converter drift')
    plan=data['packages/campaign/chapter05_plans/source.plan.json'];stage=plan['stages'][stage_id]
    native=stage['native_document'];ballista=bound(ballista_path,ballista_sha)
    meta=ballista.get('manifest',{}).get('metadata',{})
    if stage_id not in meta.get('native_predefined_profiles',{}):raise ValueError('Missing actual ballista predefined profile')
    profile=deepcopy(meta['native_predefined_profiles'][stage_id])
    modules=[(label,data[path]) for label,path in [('ordinary','packages/campaign/chapter05_units/ordinary.reference_model.json'),
        ('regeneration','packages/campaign/chapter05_units/regenerating/model.json'),('special','packages/campaign/chapter05_units/special/model.selection_settle.reference.json'),
        ('mephi','packages/campaign/chapter05_boss/mephi/model.json'),('fixed12','packages/campaign/roster/fixed12.m26.reference_module.json')]]
    modules.append(('ballista',ballista));native_for_compose=deepcopy(native);branch_programs={}
    if native.get('branches'):
        faust=bound(faust_path,faust_sha);modules.append(('faust',faust))
        branch=data['packages/campaign/chapter05_boss/faust/branch.reference.json']
        if native['branches']!={branch['branch_id']:branch['native_branch']}:raise ValueError('Native branch actions drift')
        if meta.get('registered_keys',{}).get(stage_id)!=branch['required_registrations']:
            raise ValueError('All source hidden ballista registrations required')
        branch_programs[branch['branch_id']]=deepcopy(branch['program']);native_for_compose['branches']={}
    definitions,_=compose_modules(modules);units={}
    for definition in definitions.values():
        vid=definition.get('metadata',{}).get('native_variant_id',definition.get('metadata',{}).get('native_variant'))
        reference=definition.get('metadata',{}).get('native_reference')
        if not vid and definition['kind']=='entity' and reference is not None:
            matches=[ident for ident,row in plan['variants'].items() if row['native_reference']==reference]
            if len(matches)!=1:raise ValueError('Entity native reference is ambiguous: '+definition['id'])
            vid=matches[0]
        if definition['kind']=='entity' and vid:
            if vid in units:raise ValueError('Conflicting exact variant '+vid)
            units[vid]=definition['id']
    rows=[];bindings={}
    for vid in stage['variant_ids']:
        if vid not in units:raise ValueError('Missing required native variant '+vid)
        v=plan['variants'][vid];reference=v['native_reference']
        if reference not in native['enemyDbRefs'] or reference['id'] in bindings:raise ValueError('Ambiguous native enemy reference')
        motion=v['native_enemy']['resolved']['motion'];bindings[reference['id']]={'unit':units[vid],'motion':motion}
        rows.append({'variant_id':vid,'native_reference':reference,'unit_definition':units[vid],'motion':motion})
    portal=data['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'];profiles=deepcopy(portal['scenarioDraft']['map']['tile_mechanics'])
    scene,controls=compose(native_for_compose,stage_id,bindings,profiles,predefined_profile=profile)
    if branch_programs:scene['branches']=branch_programs
    if controls:modules.append(('native_controls',{'definitions':controls}))
    roster=data['packages/campaign/roster/fixed12.m26.reference_module.json'];scene['roster']=deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    for label,package in modules:
        for key,value in package.get('manifest',{}).get('metadata',{}).get('stage_rules',{}).items():
            if key in scene['rules'] and scene['rules'][key]!=value:raise ValueError('Conflicting stage rule '+key+' from '+label)
            scene['rules'][key]=value
    modules.append(('spawn_policy',{'rules':[r for r in portal['rules'] if r['id']=='rule/m7_spawn_rectangle']}))
    result,_=reachable_content(scene,modules,manifest_id='package/reference/'+stage_id)
    s=result['scenarioDraft'];expected=(51,4,8,10) if stage_id.endswith('09') else (73,6,9,0)
    actual=sum(a.get('count',1) for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')
    if (actual,len(rows),s['parameters']['deploy_capacity'],s['resources']['dp']['initial'])!=expected:
        raise ValueError('Exact stage accounting changed')
    if s['resources']['life']['initial']!=3 or s['seed']!=native['randomSeed']:raise ValueError('Native life/seed drift')
    if definitions[s['rules']['movement.speed']]['parameters']['multiplier']!=native['options']['moveMultiplier']:
        raise ValueError('Native move multiplier not consumed')
    result['manifest']['metadata'].update(source_locks={**PINS,str(Path(ballista_path).resolve()):ballista_sha,str(Path(faust_path).resolve()):faust_sha},
        required_runtime=implementation_digest(),builder_sha=sha(Path(__file__)),variant_bindings=rows,
        source_births=actual,native_options=deepcopy(native['options']),native_predefines=deepcopy(native['predefines']),
        native_branches=deepcopy(native.get('branches')),inherited_module_metadata={label:deepcopy(p.get('manifest',{}).get('metadata',{})) for label,p in modules},
        full_stage_executed=False,client_verified=False)
    Compiler().compile(result);return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    ap.add_argument('--stage',choices=['level_main_05-09','level_main_05-10'],required=True);ap.add_argument('--ballista-module',type=Path,required=True);ap.add_argument('--ballista-sha',required=True)
    ap.add_argument('--faust-module',type=Path,required=True);ap.add_argument('--faust-sha',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    sys.path.insert(0,str(a.runtime_root.resolve()));sys.path.insert(1,str(ROOT));from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==a.expected_core
    p=build(a.stage,a.ballista_module,a.ballista_sha,a.faust_module,a.faust_sha);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf8') as f:json.dump(p,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'stage':a.stage,'sha':sha(a.output),'compiled':True,'full_stage_executed':False}))
if __name__=='__main__':main()
