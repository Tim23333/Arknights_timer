"""Exact stage/variant inventory for chapter4 without a runnable-model claim."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB,PIN
from tools.build_reference_stage_scenario_v2 import map_plan
OUT=ROOT/'packages/campaign/chapter04_plans/source.plan.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(p):return hashlib.sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def build():
    locks={};sources={}
    def read(path):
        raw=path.read_bytes();key=path.resolve().relative_to(ROOT.parent).as_posix();locks[key]=hashlib.sha256(raw).hexdigest();sources[key]=raw;return json.loads(raw)
    lock=read(ROOT/'packages/campaign/enemy_sources.lock.json');db=read(DEFAULT_DB)
    if lock['commit']!=PIN or sha(DEFAULT_DB)!=lock['sha256']:raise ValueError('Enemy DB source drift')
    manifest=read(ROOT/'packages/campaign/native_reference/reference.manifest.json')
    catalog=read(ROOT/'packages/campaign/mainline_catalog.json')
    selected=[r for r in catalog['stages'] if r['selected'] and r['chapter']==4]
    if {r['native_id'] for r in selected}!={'main_04-09','main_04-10'}:raise ValueError('Fixed chapter4 target scope changed')
    variants={};stages={};reuse={}
    for name in ('chapter01_sources/native.reference.json','chapter02_sources/native.reference.json','chapter03_sources/native.reference.json'):
        old=read(ROOT/'packages/campaign'/name);keys=set(old.get('prefabs',{}))|set(old.get('enemies',{}));reuse[name]=keys
    for name in ('04-09','04-10'):
        level='level_main_'+name;path=ROOT/'packages/campaign/native_reference'/(level+'.json');native=read(path)
        if manifest['files'][level]['sha256']!=sha(path) or manifest['files'][level]['commit']!=PIN:raise ValueError('Stage source drift')
        refs=[]
        for ref in native['enemyDbRefs']:
            enemy=resolve_enemy(db,ref);vid=enemy['native_id']+'@'+str(enemy['native_level'])+'/'+digest({'reference':ref,'resolved':enemy['resolved']})[:16]
            variants.setdefault(vid,{'variant_id':vid,'native_reference':deepcopy(ref),'native_enemy':enemy,'stages':[]})['stages'].append(level);refs.append(vid)
        counts=Counter();controls=Counter();used=set();actions=[]
        for wi,w in enumerate(native['waves']):
            for fi,f in enumerate(w['fragments']):
                for ai,a in enumerate(f['actions']):
                    record={'wave':wi,'fragment':fi,'action':ai,'native':deepcopy(a)}
                    if a['actionType']=='SPAWN':
                        matches=[v for v in refs if variants[v]['native_enemy']['native_id']==a['key']]
                        if len(matches)!=1:raise ValueError('Ambiguous exact enemy reference:'+a['key'])
                        index=a['routeIndex']
                        if type(index) is not int or not 0<=index<len(native['routes']):raise ValueError('Source route invalid')
                        record['variant_id']=matches[0];counts[a['key']]+=a['count'];used.add(index)
                    else:controls[a['actionType']]+=a['count']
                    actions.append(record)
        mp=map_plan(native);tiles=Counter(t['tileKey'] for t in mp['tiles'])
        if any(native['predefines'].get(k) for k in native['predefines']):raise ValueError('Unexpected chapter4 predefines require explicit source extraction')
        stages[level]={'native_document':native,'map_plan':mp,'variant_ids':refs,'spawn_count':sum(counts.values()),'spawn_by_key':dict(counts),
                       'control_count_by_type':dict(controls),'used_routes':sorted(used),'actions':actions,'tile_cell_counts':dict(tiles),
                       'used_checkpoint_counts':dict(Counter(c['type'] for i in used for c in native['routes'][i].get('checkpoints') or [])),
                       'normal_runes':{'mask':1,'raw':deepcopy(native.get('runes')),'runtime_consumed':False}}
    matrix=[]
    for vid,v in variants.items():
        enemy=v['native_enemy']['resolved'];key=enemy['prefabKey']
        matrix.append({'variant_id':vid,'prefab':key,'existing_exact_prefab_source_candidates':[name for name,keys in reuse.items() if key in keys],
                       'reuse_status':'Source candidate only; exact stage level/overrides/passives/frames must be compared',
                       'source_attributes':enemy['attributes'],'talent_blackboard':enemy.get('talentBlackboard'),'DB_skills':enemy.get('skills'),
                       'runtime_authored':False})
    for p in (Path(__file__),ROOT/'tools/build_mainline_dependencies.py',ROOT/'tools/build_reference_stage_scenario_v2.py'):
        locks[p.relative_to(ROOT.parent).as_posix()]=sha(p)
    for name,pin in locks.items():
        if sha(ROOT.parent/name)!=pin:raise ValueError('Source changed during inventory:'+name)
    return {'schema':'ark-sim/chapter04-source-plan/v1','fixed_commit':PIN,'source_locks':locks,'stages':stages,'variants':variants,'dependency_matrix':matrix,
            'required_new_consumers':['tile_volcano independent timing/targeting/arts packets','4-10 route teleport checkpoints and terrain pairs',
                                      'FrostNova phases/resurrection/invulnerability/tile denial and source status effects; do not infer chapter6 cold-freeze from the enemy name',
                                      'explosive slug death source ability, demon and ranged/multihit exact source targeting'],
            'runtime_created':False,'whole_stage_executed':False,'actual_client_verified':False}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Chapter4 inventory bytes changed')
    else:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'sha256':sha(OUT),'variants':len(p['variants']),'stages':{k:v['spawn_count'] for k,v in p['stages'].items()},'runnable':False}))
