"""Reusable pinned source inventory for selected future mainline chapters."""
import argparse,sys,json,hashlib,re
from copy import deepcopy
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB,PIN
from tools.build_reference_stage_scenario_v2 import map_plan
TABLE=ROOT/'packages/campaign/chapter10_source_prepare/stage_table.fixed56.source.json'
TABLE_SHA='7dc43a8193cd83fc626da366671fabd55e2d85c7be91e7fc26bb5d683a4f6920'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def build(chapter):
    locks={}
    def read(path):
        locks[str(path.resolve())]=sha(path);return json.loads(path.read_bytes())
    catalog=read(ROOT/'packages/campaign/mainline_catalog.json')
    matrix=sorted((r for r in catalog['stages'] if r['selected'] and r['chapter']==chapter),key=lambda r:r['native_sequence'])
    table_path=TABLE;assert sha(table_path)==TABLE_SHA;table=read(table_path)
    eligible={k:v for k,v in table['stages'].items() if re.fullmatch(r'main_'+str(chapter)+r'-\d+',k)
              and v.get('levelId') and v.get('difficulty')=='NORMAL'}
    lasttwo=sorted(eligible,key=lambda k:int(k.rsplit('-',1)[1]))[-2:]
    assert len(matrix)==2 and lasttwo==[r['native_id'] for r in matrix]
    manifest=read(ROOT/'packages/campaign/native_reference/reference.manifest.json')
    db_lock=read(ROOT/'packages/campaign/enemy_sources.lock.json');db=read(DEFAULT_DB)
    assert db_lock['commit']==PIN and sha(DEFAULT_DB)==db_lock['sha256']
    stages={};variants={};targets=[]
    for row in matrix:
        sid=row['native_id'];level='level_'+sid;path=ROOT/'packages/campaign/native_reference'/(level+'.json')
        native=read(path);identity=manifest['files'][level]
        assert identity['commit']==PIN and identity['sha256']==sha(path)
        fixed=eligible[sid];assert fixed['code']==row['code'] and fixed['levelId'].lower()=='obt/main/'+level
        targets.append({'native_id':sid,'display_code':row['code'],'level_asset':level,'difficulty':fixed['difficulty'],
                        'fixed_stage_row':deepcopy(fixed),'catalog_row':deepcopy(row),'asset_identity':deepcopy(identity)})
        refs=[]
        for ref in native['enemyDbRefs']:
            enemy=resolve_enemy(db,ref);vid=enemy['native_id']+'@'+str(enemy['native_level'])+'/'+digest({'reference':ref,'resolved':enemy['resolved']})[:16]
            if vid not in variants:variants[vid]={'variant_id':vid,'native_reference':deepcopy(ref),'native_enemy':enemy,'stages':[],'runtime_authored':False}
            variants[vid]['stages'].append(level);refs.append(vid)
        births=Counter();controls=Counter();actions=[];used=set();checkpoint_types=Counter();used_offsets=[]
        for wi,wave in enumerate(native['waves']):
            for fi,fragment in enumerate(wave['fragments']):
                for ai,action in enumerate(fragment['actions']):
                    record={'wave':wi,'fragment':fi,'action':ai,'native':deepcopy(action)}
                    if action['actionType']=='SPAWN':
                        found=[v for v in refs if variants[v]['native_enemy']['native_id']==action['key']];assert len(found)==1
                        route=action['routeIndex'];assert type(route)is int and 0<=route<len(native['routes'])
                        record['variant_id']=found[0];births[action['key']]+=action['count'];used.add(route)
                    else:controls[action['actionType']]+=action['count']
                    actions.append(record)
        for index in sorted(used):
            for cp in native['routes'][index].get('checkpoints') or []:
                checkpoint_types[cp['type']]+=1
                if any(cp.get('reachOffset',{}).values()):used_offsets.append({'route':index,'native_checkpoint':deepcopy(cp)})
        nonzero=sum(bool(any(r['startPosition'].values()) or any(r['endPosition'].values())) for r in native['routes'])
        assert nonzero>0 and native['mapData']['map'] and native['mapData']['tiles']
        mp=map_plan(native);tile_keys=Counter(t['tileKey'] for t in mp['tiles'])
        predefines=native['predefines'];hard=native.get('hardPredefines')
        tokens=[{'bucket':bucket,'index':i,'native_record':deepcopy(value)} for bucket,values in predefines.items() for i,value in enumerate(values or [])]
        features={'map_rows':mp['rows'],'map_cols':mp['cols'],'native_map_tile_keys':dict(tile_keys),
                  'routes':len(native['routes']),'nonzero_endpoint_routes':nonzero,'used_routes':sorted(used),
                  'used_checkpoint_types':dict(checkpoint_types),'nonzero_checkpoint_offsets':used_offsets,
                  'extra_routes_count':len(native.get('extraRoutes') or []),'waves':len(native['waves']),
                  'spawn_count':sum(births.values()),'spawn_by_key':dict(births),'control_actions':dict(controls),
                  'predefine_bucket_counts':{k:len(v) for k,v in predefines.items()},
                  'hard_predefine_bucket_counts':{k:len(v) for k,v in (hard or {}).items()},
                  'branches_preserved':deepcopy(native.get('branches')),'runes_preserved':deepcopy(native.get('runes')),
                  'optional_runes_preserved':deepcopy(native.get('optionalRunes')),'global_buffs_preserved':deepcopy(native.get('globalBuffs'))}
        stages[level]={'native_document':native,'native_document_digest':digest(native),'asset_identity':identity,
                       'map_plan':mp,'variant_ids':refs,'actions':actions,'predefine_records':tokens,
                       'features':features,'options':deepcopy(native['options']),
                       'lossless_gate':{'pinned_raw_sha_equal':True,'whole_document_embedded_equal':True,
                                        'all_routes_zero_rejected':True,'empty_dict_vs_list_preserved':True,
                                        'enemy_overrides_raw_and_defined_values_preserved':True},
                       'runtime_created':False,'simulation_passed':False}
    for path in [Path(__file__),ROOT/'tools/build_mainline_dependencies.py',ROOT/'tools/build_reference_stage_scenario_v2.py',
                 ROOT/'tools/chapter09_source_prepare/build_source_plan_v1.py',ROOT/'tools/build_chapter01_enemy_sources.py',
                 ROOT/'tools/build_chapter02_enemy_sources.py',ROOT/'tools/extract_campaign_animation_bindings.py']:
        locks[str(path.resolve())]=sha(path)
    assert all(sha(Path(path))==value for path,value in locks.items())
    gaps=[{'area':'enemy prefab/modes/passives/skills/projectile/Spine/BSON ownership closure',
           'status':'Pending exact source extraction and executable owned consumers for '+str(len(variants))+' selected variants; DB alone does not prove any behavior'},
          {'area':'predefines/global buffs/branches/environment','status':'Complete native objects retained. Their source templates, rules and lifecycle consumers require separate typed extraction and actual tests'},
          {'area':'runes/difficulty/hard predefines','status':'NORMAL selected from fixed stage table. Preserve every original rune and empty bucket, resolve its applicability before runtime composition'},
          {'area':'fixed12/base99999','status':'No override performed here. Future composition must retain native DP, slots, unitHP and controls, then change only base life to99999'}]
    return {'schema':'ark-sim/chapter-source-plan/v1','chapter':chapter,'fixed_commit':PIN,'targets':targets,'source_locks':locks,
            'stage_table_identity':{'url':'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/'+PIN+'/cn/gamedata/excel/stage_table.json',
                                     'path':str(table_path),'sha256':sha(table_path),'bytes':table_path.stat().st_size},
            'stages':stages,'variants':variants,'dependency_matrix':[{'variant_id':v['variant_id'],
                 'prefab':v['native_enemy']['resolved']['prefabKey'],'source_attributes':v['native_enemy']['resolved']['attributes'],
                 'talent_blackboard':v['native_enemy']['resolved'].get('talentBlackboard'),
                 'DB_skills':v['native_enemy']['resolved'].get('skills'),'runtime_authored':False} for v in variants.values()],
            'required_consumers_and_gaps':gaps,'rejected_sources':['Old lossy local LevelData/zero-route projections are not source inputs'],
            'runtime_created':False,'simulation_passed':False,'whole_stage_executed':False,'client_verified':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--chapter',type=int,choices=range(11,18),required=True)
    args=parser.parse_args();value=build(args.chapter)
    folder=ROOT/('packages/campaign/chapter'+str(args.chapter)+'_source_prepare');folder.mkdir(parents=True,exist_ok=True)
    validation=ROOT/('validation/campaign/chapter'+str(args.chapter)+'_source_prepare');validation.mkdir(parents=True,exist_ok=True)
    path=folder/'source.plan.v1.json';assert not path.exists()
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    loaded=json.loads(path.read_bytes());assert loaded==value
    for level,stage in loaded['stages'].items():
        assert stage['native_document']==json.loads((ROOT/'packages/campaign/native_reference'/(level+'.json')).read_bytes())
    receipt={'schema':'ark-sim/chapter-source-plan-receipt/v1','chapter':args.chapter,'plan_path':path.relative_to(ROOT).as_posix(),'plan_sha256':sha(path),
             'helper_sha256':sha(Path(__file__)),'targets':[{k:t[k] for k in ['native_id','display_code','level_asset']} for t in value['targets']],
             'stages':{k:v['features'] for k,v in value['stages'].items()},'variant_count':len(value['variants']),
             'source_guard_current':all(sha(Path(k))==v for k,v in value['source_locks'].items()),
             'native_documents_roundtrip_exact':True,'no_simulation_started':True,'runtime_created':False,'simulation_passed':False}
    result=validation/'source.plan.receipt.v1.json';assert not result.exists();result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'plan_sha256':sha(path),'receipt_sha256':sha(result),'variants':len(value['variants']),
                      'targets':receipt['targets'],'births':{k:v['features']['spawn_count'] for k,v in value['stages'].items()},'runtime_created':False}))
if __name__=='__main__':main()
