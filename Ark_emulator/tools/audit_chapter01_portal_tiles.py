"""Exact portal prefab and native route associations; no runtime tile rename."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.build_chapter01_enemy_sources import NativeAssets,identity
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter01_sources/native.reference.json'
ASSET=ROOT.parent/'data/battle/prefabs/[uc]tiles.ab_unpacked/CAB-a3035ec54e4c62f1271965a646b6fe4e'
OUTPUT=ROOT/'validation/campaign/chapter01_portal_source_audit.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert sha(SOURCE)=='a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd'
    stage=json.loads(SOURCE.read_bytes())['stages']['level_main_01-12'];native=stage['native_level_document'];m=native['mapData'];rows=len(m['map'])
    tiles=[]
    for i,tile in enumerate(m['tiles']):
        if tile['tileKey'] not in ('tile_telin','tile_telout'):continue
        cells=[{'matrix_cell':{'row':r,'col':c},'route_native_position':{'row':rows-1-r,'col':c}} for r,row in enumerate(m['map']) for c,k in enumerate(row) if k==i]
        tiles.append({'pointer':f'/stages/level_main_01-12/native_level_document/mapData/tiles/{i}','palette_index':i,'raw':deepcopy(tile),'cells':cells})
    n=NativeAssets();objects,trees,_=n.load(ASSET);prefabs=[]
    for go in objects.values():
        if go.type.name!='GameObject':continue
        raw=go.read_typetree()
        if raw['m_Name'] not in ('tile_telin','tile_telout'):continue
        components=[]
        for entry in raw['m_Component']:
            o=objects[entry['component']['m_PathID']];v=o.read_typetree();c={'path_id':o.path_id,'type':o.type.name,'raw':v}
            if o.type.name=='MonoBehaviour':c['script_ref'],c['native_class']=n.script(v['m_Script'],ASSET)
            components.append(c)
        prefabs.append({'name':raw['m_Name'],'game_object_path_id':go.path_id,'raw_game_object':raw,'components':components})
    assert len(prefabs)==2 and all([c['native_class'] for c in p['components'] if c['type']=='MonoBehaviour']==['Tile'] for p in prefabs)
    def tile_at(pos):
        r,c=rows-1-pos['row'],pos['col'];return m['tiles'][m['map'][r][c]]['tileKey']
    associations=[]
    for ri,route in enumerate(native['routes']):
        cp=route.get('checkpoints') or [];position=route['startPosition'];pending=None;waits=[]
        for ci,c in enumerate(cp):
            if c['type']=='MOVE':position=c['position']
            elif c['type']=='DISAPPEAR':pending={'entry_checkpoint':ci,'entry_nominal_position':deepcopy(position),'entry_tile':tile_at(position),'entry_raw':deepcopy(c)};waits=[]
            elif c['type']=='WAIT_FOR_SECONDS' and pending is not None:waits.append(c['time'])
            elif c['type']=='APPEAR_AT_POS':
                assert pending is not None,'unpaired appear'
                pending.update({'route_index':ri,'exit_checkpoint':ci,'exit_position':deepcopy(c['position']),'exit_tile':tile_at(c['position']),
                    'exit_raw':deepcopy(c),'hidden_wait_seconds':waits,'route_pointer':f'/stages/level_main_01-12/native_level_document/routes/{ri}'})
                associations.append(pending);pending=None;position=c['position']
        assert pending is None,'unpaired disappear'
    assert associations and all(x['entry_tile']=='tile_telin' and x['exit_tile']=='tile_telout' for x in associations)
    used_routes=sorted({a['routeIndex'] for w in native['waves'] for f in w['fragments'] for a in f['actions'] if a.get('actionType')=='SPAWN'})
    assert all(x['route_index'] in used_routes for x in associations)
    return {'schema':'ark-sim/chapter01-portal-source-audit/v1','formal_approval':False,'runtime_modified':False,
        'source':{'path':str(SOURCE),'sha256':sha(SOURCE)},'tile_asset':identity(ASSET),'extractor_sha256':sha(Path(__file__)),
        'native_level_asset':stage['native_level'],'tiles':tiles,'prefabs':prefabs,'script_sources':n.scripts,
        'route_associations':associations,'used_spawn_route_indices':used_routes,'raw_routes':native['routes'],
        'evidence':'Both exact prefab MonoScripts resolve to generic Tile, with no dedicated portal component or pair key in these serialized objects. Level portal blackboard/effects are null.',
        'proposed_model':'Explicit route_driven_portal declaration retains tile_telin/tile_telout identity/pass/build flags; only authored DISAPPEAR/WAIT/APPEAR changes visibility/position, no nearest-pair inference or entry-trigger rewrite.',
        'client_pending':['Native generic Tile/Enemy disappear method bodies and visuals were not recovered; absence of dedicated serialized portal component is not proof of absence of all native key dispatch.'],
        'model_gate_requirements':['Validate declared portal tile profiles and source map flags','Check each used route hide/appear pairing and entry/exit coordinates with bottom-up conversion',
          'CP/command replay hidden WAIT and appearance relocation','No invented actor/death/spawn or duplicate movement-distance packet on teleport',
          'Reject nonempty blackboard/effects/unknown portal profile rather than ignoring']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();j=build();raw=(json.dumps(j,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if a.check:assert OUTPUT.read_bytes()==raw
    else:OUTPUT.write_bytes(raw)
    print(json.dumps({'portal_cells':len(j['tiles']),'route_pairs':len(j['route_associations']),
        'routes':sorted({x['route_index'] for x in j['route_associations']}),'wait_values':sorted({w for x in j['route_associations'] for w in x['hidden_wait_seconds']}),
        'prefab_classes':[[c['native_class'] for c in p['components'] if c['type']=='MonoBehaviour'] for p in j['prefabs']],
        'sha256':sha(OUTPUT)},ensure_ascii=False))
