"""Close serialized/BSON references and report exact source/body boundaries."""
import sys,json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.build_chapter01_enemy_sources import bson_source
P=ROOT/'packages/campaign/chapter10_source_prepare'
V=ROOT/'validation/campaign/chapter10_source_prepare'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()

def scan(value,templates,projectiles,spawns,path='source'):
    if isinstance(value,dict):
        if isinstance(value.get('templateKey'),str) and value['templateKey']:templates.add(value['templateKey'])
        if value.get('key')=='projectile' and value.get('valueStr'):projectiles.add(value['valueStr'])
        for key,child in value.items():
            if key in {'_projectileKey','projectileKey','_projectilePrefabKey','_projectileToEmit','_projectileToSpawn'} and isinstance(child,str) and child:projectiles.add(child)
            if key in ['_characterKey','_enemyKey','_unitKey','_tokenKey'] and isinstance(child,str) and child:
                spawns.append({'path':path+'.'+key,'key':child})
            if key=='SerializedState' and isinstance(child,str) and child:
                try:parsed=json.loads(child)
                except json.JSONDecodeError as error:raise ValueError('Malformed native SerializedState at '+path) from error
                scan(parsed,templates,projectiles,spawns,path+'.decodedSerializedState')
            else:scan(child,templates,projectiles,spawns,path+'.'+key)
    elif isinstance(value,list):
        for i,child in enumerate(value):scan(child,templates,projectiles,spawns,path+'['+str(i)+']')

def main():
    files=[P/name for name in ['source.plan.v1.json','enemies.native.v1.json','predefines.native.v3.json','environment.native.v1.json']]
    documents=[json.loads(path.read_bytes()) for path in files];before={str(path):sha(path) for path in files}
    templates=set();projectiles=set();spawns=[]
    for path,value in zip(files,documents):scan(value,templates,projectiles,spawns,path.name)
    rounds=[]
    for _ in range(32):
        closed=bson_source(templates);new=set(templates);found=set(projectiles);nextspawns=[]
        scan(closed['templates'],new,found,nextspawns,'transitiveBSON')
        rounds.append({'requested_templates':len(templates),'found_templates':len(closed['templates']),'added_templates':sorted(new-templates)})
        projectiles|=found;spawns.extend(nextspawns)
        if new==templates:break
        templates=new
    else:raise ValueError('BSON closure did not stabilize')
    output=P/'bson.transitive.v2.json';assert not output.exists();output.write_text(json.dumps(closed,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    plan,enemies,tokens,environment=documents;matrix=[]
    for vid,variant in enemies['variants'].items():
        key=variant['prefab_key'];prefab=enemies['prefabs'][key]
        classes=Counter(c['native_class'] for c in prefab.get('components',{}).values())
        hooks=[{'path_id':pid,'class':c['native_class'],'gameobject':c.get('gameobject_name'),
                'field_names':list(c['raw'])} for pid,c in prefab.get('components',{}).items()
               if any(x in c['native_class'] for x in ['Ability','Skill','Talent','Checker','Selector'])]
        matrix.append({'variant_id':vid,'stages':variant['stages'],'fixed_level':variant['native_enemy']['native_level'],
            'stage_override':variant['native_reference'].get('overwrittenData'),'prefab':key,
            'prefab_sha256':prefab.get('source',{}).get('sha256'),'classes':dict(classes),
            'modes':variant.get('modes'),'passive_and_skill_sources':variant.get('passive_and_skill_components'),
            'ownership_components':hooks,'animation_status':enemies['animations'][key].get('status'),
            'source_gap':variant.get('source_gap'),'native_method_bodies_recovered':False,'consumer_implemented':False})
    unresolved_projectiles=sorted(projectiles-set(enemies['projectiles'])-set(tokens['projectiles']))
    unique_spawns={json.dumps(x,sort_keys=True):x for x in spawns}
    detail={'schema':'ark-sim/chapter10-source-detail/v1','stage_priority':'level_main_10-14 / display10-16',
        'fixed_commit':plan['fixed_commit'],'enemy_dependency_matrix':matrix,
        'predefined_dependencies':tokens['stages'],'token_classes':{k:dict(Counter(c['native_class'] for c in v.get('components',{}).values())) for k,v in tokens['prefabs'].items()},
        'selected_skill_classes':{k:dict(Counter(c['native_class'] for c in v.get('components',{}).values())) for k,v in tokens['skill_prefabs'].items()},
        'map_classes':{k:dict(Counter(c['native_class'] for c in v.get('components',{}).values())) for k,v in environment['prefabs'].items()},
        'BSON_rounds':rounds,'BSON_missing':closed['missing_templates'],'projectile_string_dependencies':sorted(projectiles),
        'projectile_exact_closure_missing':unresolved_projectiles,'spawn_string_dependencies':list(unique_spawns.values()),
        'version_policy':{'fixed_tables_levels':plan['fixed_commit'],'token_AB':'Frozen20250327 battle_prefabs_tokens.20250327.ab; exact separate SHA, not fixed56-aligned',
                          'enemy_tile_skill_projectile_assets':'Local serialized CAB source paths/SHA retained; no client version inferred from class names',
                          'method_bodies':'MonoScript names/raw fields only; native methods, target geometry/hook execution algorithms and client fidelity not recovered'},
        'actual_gaps':['All14 source consumers not implemented by extraction','DB skill rows require actual prefab ownership; no extra DB skill activation invented',
                       'Gunctrl global unique ability/current blocker-or-maxHP cannon selection and owned target lifecycle need source consumer design',
                       'Tile fence/telin/out have Tile raw components only; route DISAPPEAR/APPEAR_AT_POS and map operands retained, runtime interpretation pending',
                       'Transitive projectile/spawn strings are explicit dependencies; any missing closure is recorded, never substituted'],
        'runtime_created':False,'simulation_passed':False,'client_verified':False}
    path=P/'source.detail.v2.json';assert not path.exists();path.write_text(json.dumps(detail,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert before=={str(path):sha(path) for path in files}
    receipt={'schema':'ark-sim/chapter10-closed-source-receipt/v1','source_inputs_before':before,'source_inputs_after':{str(path):sha(path) for path in files},
        'outputs':[{'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size} for path in files[1:]+[output,path]],
        'variants':len(matrix),'prefabs':len(enemies['prefabs']),'exact_animation_sources':sum(v.get('status')=='exact_source_bound_spine' for v in enemies['animations'].values()),
        'enemy_projectiles':len(enemies['projectiles']),'token_prefabs':list(tokens['prefabs']),'token_skill_prefabs':list(tokens['skill_prefabs']),
        'tiles':list(environment['prefabs']),'BSON_count':len(closed['templates']),'BSON_missing':closed['missing_templates'],
        'projectile_missing':unresolved_projectiles,'spawn_string_dependencies':list(unique_spawns.values()),
        'helpers':{path.relative_to(ROOT).as_posix():sha(path) for path in sorted((ROOT/'tools/chapter10_source_prepare').glob('*.py'))},
        'no_runtime_or_simulation':True,'source_only':True}
    p=V/'closed1.receipt.v2.json';assert not p.exists();p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'receipt_sha256':sha(p),'detail_sha256':sha(path),'variants':len(matrix),'BSON_templates':len(closed['templates']),'BSON_missing':closed['missing_templates'],'projectile_missing':unresolved_projectiles,'runtime_created':False}))
if __name__=='__main__':main()
