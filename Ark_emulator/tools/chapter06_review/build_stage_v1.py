"""Exact C6 joins with custom source providers and native training exception."""
import argparse,hashlib,json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PINS=ROOT/'packages/campaign/chapter06_join/source.pins.json'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bound(path,pin):
    if sha(path)!=pin:raise ValueError('Frozen content drift '+str(path))
    return json.loads(Path(path).read_bytes())


def providers():
    from tools.chapter06.cold.policies import providers as cold
    from tools.chapter06_npcs.providers_v2 import providers as npcs
    return {**cold(),**npcs()}


def build(stage_id,boss_path,boss_sha):
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter06_review.stage_converter_v7 import compose,exact
    from tools.chapter06_review.story_keys_v5 import convert,digest,SCHEMA,POLICY
    from tools.campaign_content_composition_v2 import compose_modules,reachable_content
    pins=json.loads(PINS.read_bytes());data={p:bound(ROOT/p,pin) for p,pin in pins.items() if p.endswith('.json')}
    for p,pin in pins.items():
        if sha(ROOT/p)!=pin:raise ValueError('Source/helper drift '+p)
    plan=data['packages/campaign/chapter06_plans/source.plan.json']
    if stage_id not in plan['stages']:raise ValueError('Unsupported source chapter6 stage')
    stage=plan['stages'][stage_id];native=deepcopy(stage['native_document'])
    boss=bound(boss_path,boss_sha)
    module_paths=['packages/campaign/roster/fixed12.m26.reference_module.json','packages/campaign/chapter06_cold/model.json']
    module_paths += ['packages/campaign/chapter06_units/'+n for n in ['melee_v2/model.json','snmage_v3/model.json','snslime/model.json','frozen_melee/model.json','snbow_v2/model.json']]
    modules=[(p,data[p]) for p in module_paths]+[('source_boss',boss)]
    env=data['packages/campaign/chapter06_environment_consumer/module.v2.reference.json']['manifest']['metadata']
    trap=data['packages/campaign/chapter06_predefines_consumer/module.v2.reference.json']
    native_for_compose=deepcopy(native);story_profile=None;stories={};lifecycle=[]
    if stage_id=='level_main_06-14':
        modules.append(('source_frost_trap',trap));meta=trap['manifest']['metadata']
        predefined=deepcopy(meta['native_predefined_profiles'][stage_id])
        # The existing trap profile predates bucket provenance. Add it only
        # after exact matching each actual alias and raw token instance.
        for item,raw in zip(predefined['initial_entities'],native['predefines']['tokenInsts']):
            if item['registration_key']!=raw['alias'] or not exact(item['parameters']['native_instance'],raw):
                raise ValueError('Source trap instance differs')
            item['parameters']['native_bucket']='tokenInsts'
        if not exact(native['branches'],{'frstar_frosts':meta['raw_native_branch']}):
            raise ValueError('Exact native frost branch source differs')
        branches=deepcopy(meta['native_branch_programs'][stage_id]);native_for_compose['branches']={}
    else:
        npc_paths=['packages/campaign/chapter06_npcs/'+n for n in ['swllow.v2.model.json','huang.v7.model.json','amiya.v3.model.json','story_controls.v2.model.json']]
        modules += [(p,data[p]) for p in npc_paths]
        actor_map={r['inst']['characterKey']:'unit/ch6/npc/'+r['inst']['characterKey'] for r in native['predefines']['characterInsts']}
        story_profile={'schema':SCHEMA,'policy':POLICY,'native_id':stage_id,'native_document_digest':digest(native),
            'bindings':[{'bucket':'characterInsts','index':i,'activation_key':r['inst']['characterKey'],'definition':actor_map[r['inst']['characterKey']]} for i,r in enumerate(native['predefines']['characterInsts'])]}
        predefined=convert(native,stage_id,actor_map,story_key_profile=story_profile)
        story=data[npc_paths[-1]];stories={c['metadata']['native_story_key']:c for c in story['controls']};branches={}
        exitp=data['packages/campaign/chapter06_exit_accounting/reference_policy.json'];lifecycle=[exitp['actionLifecycleProfile']]
        modules.append(('source_training_exit',{'rules':exitp['rules']}))
    defs,_=compose_modules(modules);source=data['packages/campaign/chapter06_sources/native.reference.json']['variants'];units={}
    for d in defs.values():
        vid=d.get('metadata',{}).get('native_variant_id')
        if d['kind']=='entity' and vid:
            if vid in units:raise ValueError('Duplicate source variant')
            units[vid]=d
    bindings={};rows=[]
    for vid in stage['variant_ids']:
        if vid not in units:raise ValueError('Missing exact native variant '+vid)
        original=source[vid];reference=original['native_reference'];unit=units[vid]
        if reference not in native['enemyDbRefs'] or reference['id'] in bindings:raise ValueError('Ambiguous enemy source')
        raw=original['native_enemy']['resolved']['attributes'];actual=unit['components']['attributes']['base']
        for dest,key in [('max_hp','maxHp'),('atk','atk'),('def','def'),('mres','magicResistance'),('move_speed','moveSpeed')]:
            if actual[dest]!=raw[key] or type(actual[dest]) is bool:raise ValueError('Source enemy attributes changed '+vid+'/'+key)
        if unit['components']['resources']['hp']['initial']!=raw['maxHp']:raise ValueError('Enemy initial HP drift')
        bindings[reference['id']]={'unit':unit['id'],'motion':original['native_enemy']['resolved']['motion']}
        rows.append({'variant_id':vid,'native_reference':reference,'unit':unit['id']})
    profiles=deepcopy(env['native_stages'][stage_id]['converted_map']['tile_mechanics'])
    scene,controls=compose(native_for_compose,stage_id,bindings,profiles,story_controls=stories,predefined_profile=predefined,
        story_key_profile=story_profile,action_lifecycle_profiles=lifecycle)
    if branches:scene['branches']=branches
    if controls:modules.append(('source_controls',{'definitions':controls}))
    roster=data['packages/campaign/roster/fixed12.m26.reference_module.json'];scene['roster']=deepcopy(roster['manifest']['metadata']['roster'])
    scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    portal=data['packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json']
    modules.append(('source_spawn_policy',{'rules':[r for r in portal['rules'] if r['id']=='rule/m7_spawn_rectangle']}))
    speed=defs[scene['rules']['movement.speed']]
    speed=deepcopy(speed);speed['parameters']['multiplier']=native['options']['moveMultiplier']
    replacements={speed['id']:{'definition':speed,'reason':'Consume exact stage source movement multiplier','source':str(PINS)}}
    reg=providers();result,report=reachable_content(scene,modules,replacements,manifest_id='package/reference/'+stage_id,providers=reg)
    s=result['scenarioDraft'];births=sum(a.get('count',1) for w in s['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')
    expected=(50,9,10,3) if stage_id=='level_main_06-14' else (1,0,0,1)
    if (births,s['parameters']['deploy_capacity'],s['resources']['dp']['initial'],s['resources']['life']['initial'])!=expected:
        raise ValueError('Native stage accounting drift')
    result['manifest']['metadata'].update(source_locks={**pins,str(Path(boss_path).resolve()):boss_sha},source_pins_sha=sha(PINS),
        variant_bindings=rows,source_births=births,required_core=implementation_digest(),builder_sha=sha(Path(__file__)),
        native_options=deepcopy(native['options']),native_predefines=deepcopy(native['predefines']),native_branches=deepcopy(native.get('branches')),
        native_document_digest=digest(native),fixed12_selected=12,training_deployment_exception=stage_id=='level_main_06-15',
        full_stage_executed=False,client_verified=False)
    Compiler(providers=reg).compile(result);return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--expected-core',required=True)
    ap.add_argument('--stage',choices=['level_main_06-14','level_main_06-15'],required=True);ap.add_argument('--boss-module',type=Path,required=True)
    ap.add_argument('--boss-sha',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    sys.path.insert(0,str(a.runtime_root.resolve()));sys.path.insert(1,str(ROOT));from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==a.expected_core
    result=build(a.stage,a.boss_module,a.boss_sha);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'compiled':True,'sha':sha(a.output),'stage':a.stage,'full_stage_executed':False}))


if __name__=='__main__':main()
