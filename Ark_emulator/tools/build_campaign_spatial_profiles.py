"""M7 source audit and proposed spatial profiles; never integrates M6 content."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'packages/campaign/spatial.profiles.json'
LEVEL=ROOT/'packages/campaign/native_reference/level_main_00-10.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf8'))
def source_record(path):return {'path':path.relative_to(ROOT.parent).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size}


def declaration_audit(path):
    lines=path.read_text(encoding='utf8').splitlines()
    names=('RouteData','LevelData.Options','LevelData','Route','PathRequest','IPathFinding','SPFA',
        'GridPosition','MoveController','Map','IBattleRandom','BattleRandomFactory','BattleRandomWrapper','BattleController')
    wanted=re.compile(r'spawnRandomRange|spawnOffset|allowDiagonalMove|steeringEnabled|randomSeed|s_randomImp|s_randomTrivial|m_randomWrapper|GetSpawnPosition|GetSpawnOffset|GetContDirectionAfterEnd|CheckReached|CheckReachable|asLocalPosition|FromVectorPosition|MapToWorldPosition|WorldToMapPosition|WorldToGridPosition|GRID_FOUR_WAYS|GRID_EIGHT_WAYS|CalculateMoveDelta|CalculateTotalForce|_CalculateSteeringForce|_CalculateObstacleAvoidForce|_GetFootMapPosition|_steeringFactor|_maxSteeringForce|_halfBodyWidth|SEPARATION_|TILE_NEAR_THRESHOLD|RandomVector2|NextDouble|Create\(int randomSeed|_LoadGameInternal')
    result={}
    for name in names:
        regex=re.compile(r'^public (?:abstract |static |sealed )?(?:class|struct|interface) '+re.escape(name)+r'(?:\s|:|$)')
        starts=[i for i,line in enumerate(lines) if regex.match(line)]
        if len(starts)!=1:raise ValueError(f'{path.name}: type declaration missing/ambiguous: {name}')
        start=starts[0];end=next((i for i in range(start+1,len(lines)) if lines[i].startswith('// Namespace:')),len(lines))
        entries=[]
        for i in range(start,end):
            line=lines[i]
            if not wanted.search(line) or '__Hotfix' in line:continue
            kind=('empty_method_stub' if line.rstrip().endswith('{ }') else
                  'abstract_method_declaration' if 'abstract ' in line and line.rstrip().endswith(';') else
                  'property_declaration' if '{ get;' in line else 'field_or_constant_declaration')
            entries.append({'line':i+1,'text':line.strip(),'kind':kind,
                'rva_comment':lines[i-1].strip() if i>0 and '// RVA:' in lines[i-1] else None,
                'native_method_body_verified':False})
        result[name]={'type_line':start+1,'type_text':lines[start],'symbols':entries}
    return {'source':source_record(path),'types':result,
        'status':'declarations_only_no_verified_native_method_bodies',
        'warning':'RVA/hotfix signatures are not method bodies or a proven call graph.'}


def mover_sources():
    import UnityPy
    reference=ROOT/'packages/campaign/enemies.00_10.attacks.json'
    records=read(reference)['manifest']['metadata']['native_enemy_records']
    cache={};result={}
    for record in records:
        path=ROOT.parent/record['source']['source']
        if sha(path)!=record['source']['source_sha256']:raise ValueError('Frozen enemy prefab identity changed')
        if path not in cache:
            env=UnityPy.load(str(path))
            trees={o.path_id:o.read_typetree() for o in env.objects if o.type.name=='MonoBehaviour'}
            objects={o.path_id:o for o in env.objects}
            cache[path]=(objects,trees)
        objects,trees=cache[path]
        roots=[o.path_id for o in objects.values() if o.type.name=='GameObject' and o.read().m_Name==record['native_id']]
        if len(roots)!=1:raise ValueError('Exact native enemy GameObject ambiguous')
        movers=[(key,t) for key,t in trees.items() if t.get('m_GameObject',{}).get('m_PathID')==roots[0] and '_steeringFactor' in t]
        if len(movers)!=1:raise ValueError('Exact enemy MoveController field shape missing/ambiguous')
        key,tree=movers[0]
        result[record['native_id']]={'source':source_record(path),'gameobject_path_id':roots[0],
            'component_path_id':key,'script_path_id':tree['m_Script']['m_PathID'],
            'fields':{k:v for k,v in tree.items() if not k.startswith('m_')},
            'association':'component attached to exact enemy root GameObject; class inference uses serialized field shape',
            'steering_formula_verified':False}
    return {'reference':source_record(reference),'enemies':result}


def uniform_position(base,offset,ranges,samples):
    """Proposed native-xy axes -> top-down integer-center model, NOT native code."""
    for value in [*base.values(),*offset.values(),*ranges.values(),*samples.values()]:
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite numeric coordinates/samples required')
    if any(v<0 for v in ranges.values()):raise ValueError('Range halfextents must be nonnegative')
    active=[axis for axis in ('x','y') if ranges[axis]>0]
    if set(samples)!=set(active) or any(not 0<=v<1 for v in samples.values()):raise ValueError('Exactly declared active-axis samples in [0,1) required')
    delta={axis:offset[axis]+((2*samples[axis]-1)*ranges[axis] if axis in active else 0) for axis in ('x','y')}
    return {'row':base['row']-delta['y'],'col':base['col']+delta['x']}


def offline_expectations():
    cases=[({'row':4,'col':0},{'x':0,'y':0},{'x':.2,'y':.2},{'x':0,'y':0},{'row':4.2,'col':-.2}),
        ({'row':4,'col':0},{'x':.25,'y':.1},{'x':.2,'y':.3},{'x':.75,'y':.25},{'row':4.05,'col':.35}),
        ({'row':4,'col':0},{'x':0,'y':0},{'x':0,'y':0},{},{'row':4,'col':0}),
        ({'row':4,'col':0},{'x':0,'y':0},{'x':0,'y':.2},{'y':.5},{'row':4,'col':0})]
    results=[]
    for base,offset,ranges,samples,expected in cases:
        actual=uniform_position(base,offset,ranges,samples)
        if any(not math.isclose(actual[k],expected[k],abs_tol=1e-12) for k in expected):raise AssertionError('Offline model expectation failed')
        results.append({'base':base,'native_offset':offset,'range_halfextents':ranges,'supplied_samples':samples,
            'expected':expected,'actual':actual,'sample_count':len(samples),'status':'offline_model_expectation_passed'})
    rejected=0
    for ranges,samples in [({'x':-.2,'y':0},{}),({'x':.2,'y':0},{}),({'x':.2,'y':0},{'x':1}),({'x':0,'y':0},{'x':.5})]:
        try:uniform_position({'row':4,'col':0},{'x':0,'y':0},ranges,samples)
        except ValueError:rejected+=1
    if rejected!=4:raise AssertionError('Invalid model input did not fail')
    return {'cases':results,'invalid_input_cases_rejected':rejected,
        'client_comparison':False,'runtime_implementation_test':False}


def level_audit():
    level=read(LEVEL);grid=level['mapData']['map'];palette=level['mapData']['tiles'];rows=len(grid);cols=len(grid[0])
    counts=Counter(a['routeIndex'] for w in level['waves'] for f in w['fragments'] for a in f['actions']
        if a['actionType']=='SPAWN' for _ in range(a['count']))
    def point(p):
        r,c=rows-1-p['row'],p['col']
        inside=type(r) is int and type(c) is int and 0<=r<rows and 0<=c<cols
        tile=palette[grid[r][c]] if inside else None
        return {'native_grid':p,'M6_model_grid':{'row':r,'col':c},'inside_index_table':inside,
            'at_outer_index_border':inside and (r in (0,rows-1) or c in (0,cols-1)),
            'tile_record':tile}
    route_rows=[{'index':i,'spawn_count':counts[i],'raw_route':r,
        'start':point(r['startPosition']),'end':point(r['endPosition'])} for i,r in enumerate(level['routes'])]
    portals=[{'model_grid':{'row':r,'col':c},'native_grid':{'row':rows-1-r,'col':c},'tile_record':palette[idx]}
        for r,row in enumerate(grid) for c,idx in enumerate(row) if palette[idx]['tileKey'] in ('tile_start','tile_end','tile_flystart')]
    nonzero=sum(counts[i] for i,r in enumerate(level['routes']) if r['spawnRandomRange']['x'] or r['spawnRandomRange']['y'])
    budget=sum(counts[i]*sum(r['spawnRandomRange'][a]>0 for a in ('x','y')) for i,r in enumerate(level['routes']))
    if sum(counts.values())!=35 or nonzero!=33 or budget!=66:raise ValueError('0-10 declared spatial input changed')
    return {'source':source_record(LEVEL),'level_id':level['levelId'],'map_shape':{'rows':rows,'cols':cols},
        'native_random_seed':level['randomSeed'],'steering_enabled':level['options']['steeringEnabled'],
        'reachable_check_ignore_start_tile':level['options']['reachableCheckIgnoreStartTile'],
        'routes':route_rows,'portal_tiles':portals,'spawn_count':sum(counts.values()),
        'nonzero_range_spawn_count':nonzero,'proposed_active_axis_sample_budget':budget,
        'budget_is_native_proven':False,'native_map_block_edges':level['mapData'].get('blockEdges')}


def historical_model_reference():
    path=ROOT/'ark_emulator/core/battle.py';text=path.read_text(encoding='utf8');tree=ast.parse(text)
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='spawn_enemy')
    segment=ast.get_source_segment(text,node)
    return {'source':source_record(path),'function':'spawn_enemy','line':node.lineno,
        'source_text':segment,'source_text_sha256':hashlib.sha256(segment.encode()).hexdigest(),
        'status':'historical_V1_model_reference_not_native_method_body','imported_or_executed':False}


def build():
    return {'schema':'ark-sim/spatial-source-proposals/v1','status':'source_audit_with_proposed_replaceable_models',
        'client_validated':False,'runtime_integrated':False,'formal_stage_approved':False,
        'builder':source_record(Path(__file__)),
        'level':level_audit(),'dump_declarations':[declaration_audit(ROOT.parent/'Ark_data/dump.cs'),
            declaration_audit(ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs')],
        'raw_enemy_movers':mover_sources(),'historical_model_reference':historical_model_reference(),
        'model_profiles':{
            'spawn':{'id':'cartesian_uniform_halfextent_native_xy_to_topdown_v1','status':'proposed_model',
                'distribution':'independent axis uniform [-range,+range), declared halfextent interpretation',
                'formula':{'col':'base.col + offset.x + (2*u_x-1)*range.x',
                           'row':'base.row - offset.y - (2*u_y-1)*range.y'},
                'ranges_are_magnitudes':True,'axis_order':['x','y'],'zero_range_consumes_no_sample':True,
                'model_stream':'spawn','kernel_algorithm_choice':'python-mt19937/sha256-stream-seed-v1',
                'root_seed_choice':953816614,'seed_role':'explicit model root seed default from source value; caller overrides logged',
                'sampling_owned_by_kernel':True,'pure_rule_consumes_no_rng':True,'atomic_with_entity_creation':True,
                'native_distribution_stream_seed_and_consumption_verified':False},
            'path':{'id':'eight_neighbor_no_corner_cut_v1','status':'proposed_model',
                'walk_connectivity':'8 when allowDiagonalMove else4','costs':{'cardinal':1,'diagonal':'sqrt(2)'},
                'corner_rule':'both adjacent cardinal cells and intervening declared edge crossings must be passable',
                'tie_policy':'explicit deterministic row/col ordering; no hidden RNG',
                'fly':'direct to each declared checkpoint; no ground wall detour',
                'wait':'all WAIT checkpoints retained; cannot be shortcut by geometric routing',
                'portal_policy':'use explicit route endpoints and cell masks, not tileKey equality',
                'native_SPFA_cost_ties_corner_rules_verified':False},
            'steering':{'id':'none_until_calibrated_v1','status':'proposed_model',
                'native_option_preserved':True,'steering_enabled_true_not_claimed_implemented':True,
                'known_prefab_constants_are_not_a_force_formula':True}},
        'interface_proposal':{
            'spawn.position':{'inputs':['base_position(model integer-center space)','native spawnOffset(x,y)',
                'native spawnRandomRange(x,y)','declared sample records(axis,value)','coordinate policy'],
                'outputs':['position(row,col)','audit choice/profile/axis signs/consumed sample identities'],
                'state_boundary':'sample+compute+create must be one outer atomic operation'},
            'spatial.path':{'inputs':['motion mode','allowDiagonalMove','visit flags','checkpoint sequence',
                'tile passability masks','blocked edges','explicit path profile'],
                'outputs':['ordered waypoints','cost/distance','profile identity'],
                'must_not_assume':'Map/Route native SPFA body reconstructed'}},
        'offline_expectations':offline_expectations(),
        'pending':['native_GetSpawnPosition_and_GetSpawnOffset_method_bodies','native_RandomVector2_distribution_and_stream',
            'native_zero_axis_consumption_and_axis_order','native_stage_seed_to_battle_and_Map_rng_binding',
            'native_SPFA_diagonal_corner_cost_and_tie_policy','native_steering_obstacle_and_separation_force_composition',
            'native_GridPosition_world_transform_and_exit_reach_threshold','local_dump_vs_prefab_version_alignment']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    value=build()
    if args.check:
        if not OUTPUT.exists() or read(OUTPUT)!=value:raise SystemExit('Spatial source/profile artifact changed')
    else:OUTPUT.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('M7 source/profile proposal:35 spawns,33 nonzero-range;66 samples is model choice, not native proof.')
