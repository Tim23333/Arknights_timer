"""Offline source checks and explicit contact math profile, no V1 execution."""
from pathlib import Path
import hashlib,json,sys,argparse
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'packages/campaign/chapter02_tiles/source.reference.json'
OUT=ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    import UnityPy
    j=json.loads(SOURCE.read_bytes());locks={str(SOURCE.relative_to(ROOT)):sha(SOURCE)}
    for key,expected in j['source_locks'].items():
        path=(ROOT/key).resolve();actual=sha(path)
        if actual!=expected:raise ValueError('frozen source changed: '+key)
        locks[key]=actual
    p=j['prefabs']['tile_hole'];path=ROOT.parent/p['source']['path']
    env=UnityPy.load(str(path));objects={o.path_id:o for o in env.objects}
    rows=[(int(pid),row) for pid,row in p['components'].items() if row['native_class']=='HoleTile']
    if len(rows)!=1:raise ValueError('HoleTile actual component ambiguous')
    pid,row=rows[0];actual=objects[pid].read_typetree()
    if actual!=row['raw']:raise ValueError('HoleTile frozen raw differs from actual Unity typetree')
    script=j['scripts'][row['script_key']];script_env=UnityPy.load(str(ROOT.parent/script['source']['path']))
    script_objects={o.path_id:o for o in script_env.objects};script_actual=script_objects[script['path_id']].read_typetree()
    if script_actual!=script['raw'] or script_actual['m_ClassName']!='HoleTile':raise ValueError('actual script pointer is not HoleTile')
    go=objects[actual['m_GameObject']['m_PathID']].read()
    if pid not in [x.component.path_id for x in go.m_Component]:raise ValueError('HoleTile component not on actual root')
    stage_cells={}
    for name,stage in j['stages'].items():
        path=ROOT/f'packages/campaign/native_reference/level_main_{name}.json';level=json.loads(path.read_bytes());cells=[]
        for native_r,indices in enumerate(level['mapData']['map']):
            for col,index in enumerate(indices):
                raw=level['mapData']['tiles'][index]
                if raw['tileKey']=='tile_hole':cells.append({'native_row':native_r,'model_row':len(level['mapData']['map'])-1-native_r,'col':col,'tile_index':index,'raw':raw})
        stage_cells[name]=cells
    profile={'type':'contact_lifecycle','rule':'rule/chapter02_ground_fall','parameters':{},'normal_path_passable':False,
        'forced_contact_passable':True,'appearance_contact_passable':True,'health_policy':'zero','death_reason':'dead','reevaluate_each_tick':False}
    return {'schema':'ark-sim/contact-model-profile/v1','status':'declared_reference_based_model','source_locks':locks,
        'actual_unity_component':{'path_id':pid,'class':script_actual['m_ClassName'],'gameobject_path_id':actual['m_GameObject']['m_PathID'],'raw':actual,'actual_script':script_actual},'native_stage_cells':stage_cells,
        'reference':{'url':'https://prts.wiki/w/%E4%BD%9C%E6%88%98%E6%9C%BA%E5%88%B6','read_date':'2026-10-03',
            'paraphrase':'Ground enemies can fall on tile entry, completed appearance, or movement-mode change; failed death checks and special rechecks require distinct policies.',
            'source_kind':'community_reference_requested_by_user','client_observation':False},
        'rules':[{'id':'rule/chapter02_ground_fall','kind':'rule','contract':'tile.contact','implementation':{'type':'expression','expression':"inputs.motion_mode == 0 and inputs.ready and 'enemy' in inputs.entity.tags"}}],
        'tile_mechanics':{'tile_hole':profile},'profile_choices':{'cell_projection':'half_up_point','normal_path':'exclude rather than native historical high-cost pathfinding',
            'forced_motion':'enter contact cell, stop at first eligible contact; wall/map edge still clip','HP':'zero with no damage packet',
            'kill_count':'enemy dead lifecycle count; no combat.kill/caster credit','birth':'Buff.contact_flags.defer_fall half-open protection',
            'environment_source':'actual displacement initiator when present, null for birth/route/appearance; ownership preserved',
            'failed_death':'replace tile.contact Boolean rule to deny; no guessed revive algorithm'},
        'client_pending':['native point/body comparator and mathematical boundary epsilon','normal path cost rather than excluded cell','native appearance callback frame','special death immunity/revive/recheck state machine','environment attribution/talent kill-credit'],
        'actual_game_accuracy_verified':False,'formal_approved':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();v=build();raw=(json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise SystemExit('profile stale')
    else:OUT.write_bytes(raw)
    print(json.dumps({'profile_sha256':sha(OUT),'actual_source_locks':len(v['source_locks']),'hole_cells':{k:len(x) for k,x in v['native_stage_cells'].items()},'client_verified':False}))
