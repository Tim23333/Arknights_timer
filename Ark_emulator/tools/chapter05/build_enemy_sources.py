"""Offline exact prefab/Spine/projectile closure for eight chapter5 variants."""
from pathlib import Path
from copy import deepcopy
import json,hashlib,argparse,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.build_chapter01_enemy_sources import NativeAssets,find_templates,bson_source
from tools.build_chapter02_enemy_sources import exact_shared_skeleton,geometry_source
from tools.build_mainline_00_11_sources import animation_sources
from tools.extract_campaign_animation_bindings import resolve_animation,library_identity
PLAN=ROOT/'packages/campaign/chapter05_plans/source.plan.json';PIN='c33c5a199fce73ef7b7524e0d29e59eeca6eb69a7f2ebd7d8c253634b050bee6'
OUT=ROOT/'packages/campaign/chapter05_sources/native.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    import UnityPy
    raw=PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('chapter5 plan drift')
    plan=json.loads(raw);variants=deepcopy(plan['variants']);keys={v['native_enemy']['resolved']['prefabKey'] for v in variants.values()};paths={key:[] for key in keys}
    for path in sorted((ROOT.parent/'data/battle').glob('enm_pfb*.ab_unpacked/CAB-*')):
        if path.name.endswith('.resS'):continue
        for obj in UnityPy.load(str(path)).objects:
            if obj.type.name=='GameObject' and obj.read().m_Name in keys:paths[obj.read().m_Name].append(path)
    if any(len(found)!=1 for found in paths.values()):raise ValueError('exact chapter5 prefab missing/ambiguous')
    assets=NativeAssets();prefabs={};animations={};projectile_keys=set();templates=set();before=library_identity();source_locks={'Ark_emulator/packages/campaign/chapter05_plans/source.plan.json':PIN}
    old=json.loads((ROOT/'packages/campaign/chapter02_sources/native.reference.json').read_bytes());source_locks['Ark_emulator/packages/campaign/chapter02_sources/native.reference.json']=sha(ROOT/'packages/campaign/chapter02_sources/native.reference.json')
    def projectiles_in(value):
        if isinstance(value,dict):
            # Buff blackboards carry projectile IDs under valueStr; they are
            # actual dependencies even when no _projectileKey field exists.
            if value.get('key')=='projectile' and isinstance(value.get('valueStr'),str) and value['valueStr']:
                projectile_keys.add(value['valueStr'])
            for key,child in value.items():
                if 'projectile' in key.lower() and isinstance(child,str) and child:projectile_keys.add(child)
                if key=='SerializedState' and isinstance(child,str) and child:
                    try:projectiles_in(json.loads(child))
                    except json.JSONDecodeError as error:raise ValueError('Invalid source SerializedState') from error
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
        additional_animation_drivers=[]
        for pid,c in prefab['components'].items():
            if c['native_class']=='NoPreOneshotAnimation':
                bindings={}
                for field in ('_animWithPre','_animNoPre','_endAnim'):
                    if c['raw'].get(field):
                        bindings[field]=resolve_animation(c['raw'][field],a['animator']['fields']['_animations'],a['parsed'])
                additional_animation_drivers.append({'path_id':pid,'native_class':c['native_class'],'raw':deepcopy(c['raw']),
                    'bindings':bindings,'runtime_policy':'Both exact source animation branches retained; no-pre dispatch trigger and animation state must be implemented before stage acceptance'})
        v.update(prefab_key=key,root_path_id=next(pid for pid,r in prefab['components'].items() if r is root[0]),modes=modes,
                 additional_animation_drivers=additional_animation_drivers)
        passive=[{'path_id':pid,'class':c['native_class'],'raw':c['raw']} for pid,c in prefab['components'].items() if c['raw'].get('_buffs') or c['raw'].get('_additiveActiveBuffs') or 'Checker' in c['native_class'] or 'Skill' in c['native_class']]
        v['passive_and_skill_components']=passive
        matrix.append({'variant_id':vid,'exact_DB_attributes':v['native_enemy']['resolved']['attributes'],'talent_BB':v['native_enemy']['resolved'].get('talentBlackboard'),
            'modes':[{'index':m['index'],'nodes':{role:{'class':n.get('native_class'),'selectTargetSource':n.get('raw',{}).get('_selectTargetSource'),'damageType':n.get('raw',{}).get('_damageType'),
                'waitForAttackEvent':n.get('raw',{}).get('_waitForAttackEvent'),'preDelay':n.get('raw',{}).get('_preDelay'),'timeMode':n.get('raw',{}).get('_timeMode'),
                'frames':[e['frame'] for e in (n.get('animation_binding') or {}).get('events',[]) if e['name']=='OnAttack'],'projectile':n.get('raw',{}).get('_projectileKey')}
                for role,n in m['nodes'].items()}} for m in modes],'passive_classes':[p['class'] for p in passive],
            'additional_animation_drivers':deepcopy(additional_animation_drivers),'runtime_authored':False})
    bson=bson_source(templates)
    def locks(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):source_locks[value['path']]=value['sha256']
            for v in value.values():locks(v)
        elif isinstance(value,list):
            for v in value:locks(v)
    locks(prefabs);locks(animations);locks(projectiles);locks(assets.scripts);locks(bson)
    for name in ('tools/chapter05/build_enemy_sources.py','tools/build_chapter01_enemy_sources.py','tools/build_chapter02_enemy_sources.py','tools/build_mainline_00_11_sources.py','tools/extract_campaign_animation_bindings.py'):source_locks['Ark_emulator/'+name]=sha(ROOT/name)
    return {'schema':'ark-sim/chapter05-enemy-source/v1','status':'exact_offline_source_closures_not_runtime_model','stage_plan_sha256':PIN,'source_locks':source_locks,'variants':variants,
        'prefabs':prefabs,'animations':animations,'projectiles':projectiles,'native_monoscripts':assets.scripts,'bson_templates':bson,'dependency_matrix':matrix,
        'spine_reader_before':before,'spine_reader_after':library_identity(),'runtime_created':False,'formal_approved':False,'client_verified':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();value=build();raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(exist_ok=True)
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('chapter5 enemy source stale')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'variants':len(value['variants']),'prefabs':len(value['prefabs']),'projectiles':len(value['projectiles']),'source_locks':len(value['source_locks']),'runtime':False}))
