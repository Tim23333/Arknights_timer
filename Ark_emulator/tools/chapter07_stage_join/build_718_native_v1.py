"""Exact native 7-17 composition draft; admission remains an external gate."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[2]
CORE='788f388ec892abca97c8d0cf6ca2329998768f273e66edef21bb000485492c8e'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    from ark_sim import Compiler
    from ark_sim.adapters.api import implementation_digest
    from tools.chapter07_stage_join.inventory_718_v1 import build as inventory
    from tools.chapter06_review.stage_converter_v7 import compose,exact
    from tools.campaign_content_composition_v2 import compose_modules,reachable_content
    from tools.chapter07_strength_melee.policies_v2 import providers as strength
    from tools.chapter07_predefines.policies_v1 import providers as ore
    assert implementation_digest()==CORE
    inv=inventory();stage_id='level_main_07-16';row=next(s for s in inv['stages'] if s['native_id']==stage_id)
    assert not row['missing_variants']
    source_file=ROOT/'packages/campaign/chapter07_plans/source.plan.json'
    plan=json.loads(source_file.read_bytes());stage=plan['stages'][stage_id];native=deepcopy(stage['native_document'])
    mods=[];source_locks={str(source_file):sha(source_file)}
    for name in sorted({v['module'] for v in row['available']}):
        path=ROOT/name;mods.append((name,json.loads(path.read_bytes())));source_locks[str(path)]=sha(path)
    roster_path=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json'
    ore_path=ROOT/'packages/campaign/chapter07_predefines_consumer/ore.module.v3.json'
    roster=json.loads(roster_path.read_bytes());device=json.loads(ore_path.read_bytes())
    mods += [('fixed12',roster),('native_ore',device)]
    for path in (roster_path,ore_path):source_locks[str(path)]=sha(path)
    definitions,_=compose_modules(mods)
    bindings={};variants=[]
    for v in row['available']:
        ref=v['native_reference'];assert ref in native['enemyDbRefs']
        bindings[ref['id']]={'unit':v['definition'],'motion':'WALK'}
        variants.append({'variant_id':v['variant_id'],'native_reference':ref,'unit':v['definition']})
    from tools.chapter07_join.predefines_profile_v1 import profile,declared_cards
    pre=profile(native,native['predefines'])
    mine_path=ROOT/'packages/campaign/chapter07_predefines_consumer/mine.module.v2.json'
    story_path=ROOT/'packages/campaign/chapter07_predefines_consumer/story.controls.v2.json'
    mine=json.loads(mine_path.read_bytes());story=json.loads(story_path.read_bytes())
    mods += [('native_mine',mine),('native_story',story)]
    for path in (mine_path,story_path):source_locks[str(path)]=sha(path)
    scene,controls=compose(native,stage_id,bindings,{},story_controls={c['metadata']['native_story_key']:c for c in story['controls']},predefined_profile=pre)
    scene['cards']=declared_cards(pre)
    assert scene['cards']==['unit/ch7/predefined/mine/level1'] and pre['resources']['stock_ch7_mine']=={'initial':15,'capacity':15}
    scene['roster']=deepcopy(roster['manifest']['metadata']['roster'])
    scene['rules']=deepcopy(roster['manifest']['metadata']['stage_rules'])
    if controls:mods.append(('native_info_controls',{'definitions':controls}))
    spawn_path=ROOT/'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json'
    spawn=json.loads(spawn_path.read_bytes());mods.append(('source_spawn_rectangle',{
        'rules':[r for r in spawn['rules'] if r['id']=='rule/m7_spawn_rectangle']}))
    source_locks[str(spawn_path)]=sha(spawn_path)
    speed_id=scene['rules']['movement.speed'];speed=deepcopy(definitions[speed_id])
    speed['parameters']['multiplier']=native['options']['moveMultiplier']
    replacements={speed_id:{'definition':speed,'reason':'Exact native stage moveMultiplier', 'source':str(source_file)}}
    from tools.chapter07_boss.policies_v2 import providers as boss
    from tools.chapter07_ranged_consumers.policies_v1 import providers as ranged
    from tools.chapter07_ranged_consumers.mortar_box_v2 import mortar_box
    reg={**strength(),**ore(),**boss(),**ranged(),'reference.c7.mortar_box':{'callable':mortar_box,'version':'2'}}
    result,_=reachable_content(scene,mods,replacements,
        manifest_id='package/ch7/native_draft/'+stage_id,providers=reg)
    actual_births=sum(a.get('count',1) for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')
    assert actual_births==stage['spawn_count']==45
    assert scene['parameters']['deploy_capacity']==9 and scene['resources']['dp']['initial']==10 and scene['resources']['life']['initial']==3
    assert exact(result['scenarioDraft']['roster'],roster['manifest']['metadata']['roster'])
    result['manifest']['metadata'].update(
        source_locks=source_locks,variant_bindings=variants,source_births=actual_births,
        native_document_digest=hashlib.sha256(json.dumps(native,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        native_options=deepcopy(native['options']),native_predefines=deepcopy(native['predefines']),
        required_core=CORE,builder_sha=sha(Path(__file__)),stage_export_allowed=False,
        admission_status='source_composition_draft_only',
        pending_model_gaps=['Current-core independent fullsource mechanism gates for every selected consumer',
                            'Ore native end/cancel and reference clock policies formally reviewed',
                            'Exact native environment tile/reference route policy review',
                            'Whole fixed12 source run with onlybase-life99999 overlay'],
        full_stage_executed=False,client_verified=False)
    Compiler(providers=reg).compile(result)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
    value=build();args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'compiled':True,'sha':sha(args.output),'source_births':45,'formal_admitted':False}))


if __name__=='__main__':main()
