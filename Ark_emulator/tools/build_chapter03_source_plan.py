"""Read-only fixed-pin stage/variant inventory with exact selected prefab sources."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import json,hashlib,argparse,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB,PIN
from tools.build_chapter01_enemy_sources import NativeAssets,find_templates,bson_source
OUT=ROOT/'packages/campaign/chapter03_plans/source.plan.json'
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def build():
    import UnityPy
    locks={};raws={}
    def read(path):
        path=path.resolve();raw=path.read_bytes();locks[path.relative_to(ROOT.parent).as_posix()]=hashlib.sha256(raw).hexdigest();raws[path]=raw;return json.loads(raw)
    enemy_lock=read(ROOT/'packages/campaign/enemy_sources.lock.json');db=read(DEFAULT_DB)
    if enemy_lock['commit']!=PIN or locks[DEFAULT_DB.resolve().relative_to(ROOT.parent).as_posix()]!=enemy_lock['sha256']:raise ValueError('enemy pin drift')
    operator_lock=read(ROOT/'packages/campaign/operator_sources.lock.json');chars=read(ROOT.parent/'unpack_work/campaign_tables/character_table.json');skills=read(ROOT.parent/'unpack_work/campaign_tables/skill_table.json')
    for name in ('character_table.json','skill_table.json'):
        row=operator_lock['files'][name]
        if row['commit']!=PIN or locks[(ROOT/row['path']).resolve().relative_to(ROOT.parent).as_posix()]!=row['sha256']:raise ValueError('device table pin drift')
    range_path=ROOT.parent/'unpack_work/campaign_tables/range_table.reference_56a.json';ranges=read(range_path)
    if locks[range_path.relative_to(ROOT.parent).as_posix()]!='a98344d688a8933c4dd7ddaae3cb76c4347295359a18b60b918042cc2542d9d9':raise ValueError('frozen range table drift')
    manifest=read(ROOT/'packages/campaign/native_reference/reference.manifest.json');old_sources={}
    for name in ('chapter01_sources/native.reference.json','chapter02_sources/native.reference.json'):
        j=read(ROOT/'packages/campaign'/name);keys=set(j.get('prefabs',{}))|set(j.get('enemies',{}));old_sources[name]={'source_identity':locks['Ark_emulator/packages/campaign/'+name],'prefab_keys':sorted(keys)}
    variants={};stages={};predefined={}
    for name in ('03-07','03-08'):
        level='level_main_'+name;path=ROOT/'packages/campaign/native_reference'/(level+'.json');native=read(path)
        row=manifest['files'][level]
        if row['sha256']!=locks[path.relative_to(ROOT.parent).as_posix()] or row['commit']!=PIN:raise ValueError('stage pin drift')
        refs=[]
        for reference in native['enemyDbRefs']:
            enemy=resolve_enemy(db,reference);key=enemy['native_id']+'@'+str(enemy['native_level'])+'/'+digest({'reference':reference,'resolved':enemy['resolved']})[:16]
            variants.setdefault(key,{'variant_id':key,'native_reference':deepcopy(reference),'native_enemy':enemy,'stages':[]})['stages'].append(level);refs.append(key)
        actions=[];spawn=Counter();controls=Counter();used=set()
        for wi,wave in enumerate(native['waves']):
            for fi,fragment in enumerate(wave['fragments']):
                for ai,action in enumerate(fragment['actions']):
                    record={'wave':wi,'fragment':fi,'action':ai,'native':deepcopy(action)}
                    if action['actionType']=='SPAWN':
                        spawn[action['key']]+=action['count'];used.add(action['routeIndex']);record['variant_candidates']=[v for v in refs if variants[v]['native_enemy']['native_id']==action['key']]
                        if len(record['variant_candidates'])!=1:record['gap']='ambiguous_variant_key_preserved'
                    else:controls[action['actionType']]+=action['count']
                    actions.append(record)
        cells=Counter(native['mapData']['tiles'][i]['tileKey'] for line in native['mapData']['map'] for i in line)
        predefined_rows=[]
        for bucket,entries in (native['predefines'] or {}).items():
            for index,item in enumerate(entries.values() if isinstance(entries,dict) else entries):
                key=item['inst']['characterKey'];character=chars[key];selected=character['skills'][item['skillIndex']]['skillId'];phase=int(item['inst']['phase'].rsplit('_',1)[1]);p=character['phases'][phase]
                predefined[key]={'character':deepcopy(character),'skill_id':selected,'skill':deepcopy(skills[selected]),'source_native_configs':[],
                    'range_sources':{row['rangeId']:deepcopy(ranges[row['rangeId']]) for row in skills[selected]['levels'] if row.get('rangeId')}}
                record={'bucket':bucket,'index':index,'native':deepcopy(item),'source_skill_id':selected,'level_above_phase_max':item['inst']['level']>p['maxLevel'],
                    'attribute_endpoints_equal':p['attributesKeyFrames'][0]['data']==p['attributesKeyFrames'][-1]['data']}
                predefined[key]['source_native_configs'].append({'stage':level,**record});predefined_rows.append(record)
        stages[level]={'native_document':native,'spawn_count':sum(spawn.values()),'spawn_by_key':dict(spawn),'control_count_by_type':dict(controls),'actions':actions,
            'variant_ids':refs,'used_routes':sorted(used),'used_checkpoint_counts':dict(Counter(c['type'] for i in used for c in native['routes'][i]['checkpoints'] or [])),
            'tile_cell_counts':dict(cells),'predefined_dependencies':predefined_rows,'normal_rune_profile':{'selected_mask':'NORMAL','active':[],'inactive_preserved':deepcopy(native['runes'])}}
    # Freeze exact selected new dependencies, retaining older bundle provenance.
    assets=NativeAssets();prefabs={};paths={}
    for path in sorted((ROOT.parent/'data/battle').glob('enm_pfb*.ab_unpacked/CAB-*')):
        if path.name.endswith('.resS'):continue
        if any(o.type.name=='GameObject' and o.read().m_Name=='enemy_1009_lurker' for o in UnityPy.load(str(path)).objects):paths.setdefault('enemy_1009_lurker',[]).append(path)
    for key,found in paths.items():
        if len(found)!=1:raise ValueError('new source prefab ambiguous '+key)
        prefabs[key]=assets.closure(found[0],key)
    if 'enemy_1009_lurker' not in prefabs:raise ValueError('lurker source missing')
    external=ROOT.parent/'unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab';raw=external.read_bytes()
    if len(raw)!=9824830 or hashlib.sha256(raw).hexdigest()!='b9f16db4bfc8e8c880a0f90a1a7a74eda3b47c2188d0a151e5239d154716d475':raise ValueError('official external token source drift')
    for key in ('trap_005_sensor','trap_001_crate'):
        prefabs[key]=assets.closure(external,key);prefabs[key]['source_version_gap']='official20250327_asset versus fixed20260929_table, retained explicitly'
    for key,pattern in [('sktok_sensor','*skills.ab_unpacked/CAB-*'),('tile_defup','*tiles.ab_unpacked/CAB-*')]:
        found=[]
        for path in (ROOT.parent/'data/battle/prefabs').glob(pattern):
            if not path.name.endswith('.resS') and any(o.type.name=='GameObject' and o.read().m_Name==key for o in UnityPy.load(str(path)).objects):found.append(path)
        if len(found)!=1:raise ValueError('selected source prefab missing/ambiguous '+key)
        prefabs[key]=assets.closure(found[0],key)
    templates=bson_source(set().union(*(find_templates(p) for p in prefabs.values())))
    for p in prefabs.values():
        path=ROOT.parent/p['source']['path'];locks[p['source']['path']]=hashlib.sha256(path.read_bytes()).hexdigest()
    for s in assets.scripts.values():locks[s['source']['path']]=s['source']['sha256']
    locks[templates['source']['path']]=templates['source']['sha256']
    dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';text=dump.read_text(encoding='utf-8-sig');locks[dump.relative_to(ROOT.parent).as_posix()]=hashlib.sha256(dump.read_bytes()).hexdigest()
    start=text.index('public enum AbnormalFlag //');end=text.index('\n}',start)+2;enum=text[start:end]
    if 'INVISIBLE = 9;' not in enum or 'CAMOUFLAGE = 17;' not in enum:raise ValueError('enum source changed')
    matrix=[]
    for key,row in variants.items():
        prefab=row['native_enemy']['resolved']['prefabKey'];reuse=[name for name,value in old_sources.items() if prefab in value['prefab_keys']]
        matrix.append({'variant_id':key,'prefab':prefab,'existing_exact_prefab_source_candidates':reuse,'reuse_status':'source_candidate_only, level/override attrs and effective abilities must be rebound; no runnable claim',
            'new_mechanism_hints':['invisible9 dynamic toggle, attack/block off, restoreDelay3'] if prefab=='enemy_1009_lurker' else [],
            'resolved_attributes':row['native_enemy']['resolved'].get('attributes'),'DB_skills':row['native_enemy']['resolved'].get('skills'),'DB_talent_blackboard':row['native_enemy']['resolved'].get('talentBlackboard')})
    locks['Ark_emulator/tools/build_chapter03_source_plan.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name in ('tools/build_mainline_dependencies.py','tools/build_chapter01_enemy_sources.py'):
        locks['Ark_emulator/'+name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    for path,raw in raws.items():
        if path.read_bytes()!=raw:raise ValueError('input changed during source read')
    return {'schema':'ark-sim/chapter03-source-plan/v1','status':'non_executable_dependency_inventory','public_data_commit':PIN,'source_locks':locks,'stages':stages,'variants':variants,'reuse_matrix':matrix,
        'old_source_candidates':old_sources,'predefined_table_subsets':predefined,'selected_native_prefabs':prefabs,'native_monoscripts':assets.scripts,'bson_templates':templates,
        'abnormal_enum':{'raw':enum,'source':dump.relative_to(ROOT.parent).as_posix()},'new_dependencies':['Sensor INVINCIBLE5 self passive and manual reveal immunity9 aura/SP15/duration20/range x-3; old assets version gap',
            'Crate five card copies/cost and legal-deploy quota, native path-block/passability/height ownership, destructible actor and killed-log source',
            'Lurker invisible9 toggle and source attack/block event clock +restore3; not camouflage17',
            'tile_defup flatDEF200 field, preserve height/buildable/passability',
            'new ordinary source modes/Spine/projectiles: jshoot,jmage,mortar,katar,handax2,shield2,gopro3,rogue2',
            'Bosslevel1 HP30000/ATK1300/threshold15000 must rebind, never copy reference50 level0 threshold5250',
            'yokai level1HP1870; undefined1450 override must remain inactive'],
        'runtime_created':False,'formal_approved':False,'client_verified':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();v=build();raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if a.check:
        if OUT.read_bytes()!=raw:raise ValueError('plan stale')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'variants':len(v['variants']),'source_locks':len(v['source_locks']),'spawns':{k:x['spawn_count'] for k,x in v['stages'].items()},'runnable':False}))
