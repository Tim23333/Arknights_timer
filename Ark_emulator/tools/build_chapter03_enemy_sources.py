"""Offline exact prefab/Spine/projectile closure for thirteen chapter3 variants."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_chapter01_enemy_sources import NativeAssets,find_templates,bson_source
from tools.build_chapter02_enemy_sources import exact_shared_skeleton,geometry_source
from tools.build_mainline_00_11_sources import animation_sources
from tools.extract_campaign_animation_bindings import resolve_animation,library_identity
PLAN=ROOT/'packages/campaign/chapter03_plans/source.plan.json';PIN='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6'
OUT=ROOT/'packages/campaign/chapter03_sources/native.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    import UnityPy
    raw=PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('chapter3 plan drift')
    plan=json.loads(raw);variants=deepcopy(plan['variants']);keys={v['native_enemy']['resolved']['prefabKey'] for v in variants.values()};paths={key:[] for key in keys}
    for path in sorted((ROOT.parent/'data/battle').glob('enm_pfb*.ab_unpacked/CAB-*')):
        if path.name.endswith('.resS'):continue
        for obj in UnityPy.load(str(path)).objects:
            if obj.type.name=='GameObject' and obj.read().m_Name in keys:paths[obj.read().m_Name].append(path)
    if any(len(found)!=1 for found in paths.values()):raise ValueError('exact chapter3 prefab missing/ambiguous')
    assets=NativeAssets();prefabs={};animations={};projectile_keys=set();templates=set();before=library_identity();source_locks={'Ark_emulator/packages/campaign/chapter03_plans/source.plan.json':PIN}
    old=json.loads((ROOT/'packages/campaign/chapter02_sources/native.reference.json').read_bytes());source_locks['Ark_emulator/packages/campaign/chapter02_sources/native.reference.json']=sha(ROOT/'packages/campaign/chapter02_sources/native.reference.json')
    def projectiles_in(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if 'projectile' in key.lower() and isinstance(child,str) and child:projectile_keys.add(child)
                projectiles_in(child)
        elif isinstance(value,list):
            for child in value:projectiles_in(child)
    for key,found in sorted(paths.items()):
        path=found[0];prefab=assets.closure(path,key);prefab['geometry_sources']=geometry_source(assets,prefab);prefabs[key]=prefab;templates|=find_templates(prefab);projectiles_in(prefab['components'])
        if key in old['prefabs']:
            prior=old['prefabs'][key]
            if prior['source']['sha256']==prefab['source']['sha256'] and {k:v['raw'] for k,v in prior['components'].items()}=={k:v['raw'] for k,v in prefab['components'].items()}:
                prefab['existing_exact_source_reference']={'package':'chapter02_sources/native.reference.json','sha256':source_locks['Ark_emulator/packages/campaign/chapter02_sources/native.reference.json'],'prefab_key':key,'raw_components_equal':True}
        try:
            a=animation_sources({key:{'source':path.relative_to(ROOT.parent).as_posix()}})[key];a['status']='exact_source_bound_spine'
        except (ValueError,KeyError) as error:
            a={'status':'native_animation_gap','error':type(error).__name__+': '+str(error)}
            if str(error)=='Skeleton identity differs from selected exact prefab':a=exact_shared_skeleton(key,path,assets);a['initial_strict_name_rejection']=str(error)
        animations[key]=a
    if library_identity()!=before:raise ValueError('shared Spine reader mutated')
    projectile_paths=[p for p in (ROOT.parent/'data/battle/prefabs').glob('*projectiles.ab_unpacked/CAB-*') if not p.name.endswith('.resS')];projectiles={}
    for key in sorted(projectile_keys):
        found=[p for p in projectile_paths if any(o.type.name=='GameObject' and o.read().m_Name==key for o in assets.load(p)[0].values())]
        if len(found)==1:projectiles[key]=assets.closure(found[0],key);projectiles[key]['geometry_sources']=geometry_source(assets,projectiles[key]);templates|=find_templates(projectiles[key])
        else:projectiles[key]={'status':'missing_or_ambiguous_projectile_source','candidate_paths':[str(p) for p in found]}
    matrix=[]
    for vid,v in variants.items():
        key=v['native_enemy']['resolved']['prefabKey'];prefab=prefabs[key];a=animations[key];root=[r for r in prefab['components'].values() if '_modes' in r['raw']]
        if len(root)!=1:raise ValueError('enemy root ambiguity '+vid)
        modes=[]
        for index,pointer in enumerate(root[0]['raw']['_modes']):
            if pointer['m_FileID']:raise ValueError('external mode must be explicitly resolved')
            mode=prefab['components'][str(pointer['m_PathID'])];nodes={}
            for role in ('_combat','_attack','_attackTrigger'):
                p=mode['raw'][role]
                if not p['m_PathID']:nodes[role]={'status':'native_null','pointer':p};continue
                if p['m_FileID']:nodes[role]={'status':'external_pointer_gap','pointer':p};continue
                node=deepcopy(prefab['components'][str(p['m_PathID'])]);node['path_id']=p['m_PathID'];binding=None
                if node['raw'].get('_animKey') and a['status'] in ('exact_source_bound_spine','exact_serialized_pointer_shared_skeleton'):
                    try:binding=resolve_animation(node['raw']['_animKey'],a['animator']['fields']['_animations'],a['parsed'])
                    except (ValueError,KeyError) as error:binding={'status':'binding_gap','error':str(error)}
                node['animation_binding']=binding;nodes[role]=node
            modes.append({'index':index,'path_id':pointer['m_PathID'],'raw':mode['raw'],'nodes':nodes})
        v.update(prefab_key=key,root_path_id=next(pid for pid,r in prefab['components'].items() if r is root[0]),modes=modes)
        passive=[{'path_id':pid,'class':c['native_class'],'raw':c['raw']} for pid,c in prefab['components'].items() if c['raw'].get('_buffs') or c['raw'].get('_additiveActiveBuffs') or 'Checker' in c['native_class'] or 'Skill' in c['native_class']]
        v['passive_and_skill_components']=passive
        matrix.append({'variant_id':vid,'exact_DB_attributes':v['native_enemy']['resolved']['attributes'],'talent_BB':v['native_enemy']['resolved'].get('talentBlackboard'),
            'modes':[{'index':m['index'],'nodes':{role:{'class':n.get('native_class'),'selectTargetSource':n.get('raw',{}).get('_selectTargetSource'),'damageType':n.get('raw',{}).get('_damageType'),
                'waitForAttackEvent':n.get('raw',{}).get('_waitForAttackEvent'),'preDelay':n.get('raw',{}).get('_preDelay'),'timeMode':n.get('raw',{}).get('_timeMode'),
                'frames':[e['frame'] for e in (n.get('animation_binding') or {}).get('events',[]) if e['name']=='OnAttack'],'projectile':n.get('raw',{}).get('_projectileKey')}
                for role,n in m['nodes'].items()}} for m in modes],'passive_classes':[p['class'] for p in passive],'runtime_authored':False})
    bson=bson_source(templates)
    def locks(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):source_locks[value['path']]=value['sha256']
            for v in value.values():locks(v)
        elif isinstance(value,list):
            for v in value:locks(v)
    locks(prefabs);locks(animations);locks(projectiles);locks(assets.scripts);locks(bson)
    for name in ('tools/build_chapter03_enemy_sources.py','tools/build_chapter01_enemy_sources.py','tools/build_chapter02_enemy_sources.py','tools/build_mainline_00_11_sources.py','tools/extract_campaign_animation_bindings.py'):source_locks['Ark_emulator/'+name]=sha(ROOT/name)
    return {'schema':'ark-sim/chapter03-enemy-source/v1','status':'exact_offline_source_closures_not_runtime_model','stage_plan_sha256':PIN,'source_locks':source_locks,'variants':variants,
        'prefabs':prefabs,'animations':animations,'projectiles':projectiles,'native_monoscripts':assets.scripts,'bson_templates':bson,'dependency_matrix':matrix,
        'spine_reader_before':before,'spine_reader_after':library_identity(),'runtime_created':False,'formal_approved':False,'client_verified':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();value=build();raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(exist_ok=True)
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('chapter3 enemy source stale')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'variants':len(value['variants']),'prefabs':len(value['prefabs']),'projectiles':len(value['projectiles']),'source_locks':len(value['source_locks']),'runtime':False}))
