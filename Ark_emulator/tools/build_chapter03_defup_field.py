"""Source DEF200 occupancy field using the existing generic field substrate."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter03_plans/source.plan.json'
PIN='d7f1f3037ccbc47b7c41346ca6b73b0e653257d479a7ea5261c6c1c1ba97c5c6'
OUT=ROOT/'packages/campaign/chapter03_tiles/defup.reference_model.json'


def build():
    from tools.build_chapter02_tile_fields import state
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Frozen chapter3 source plan drift')
    source=json.loads(raw);native=source['selected_native_prefabs']['tile_defup']
    asset=ROOT.parent/native['source']['path']
    if hashlib.sha256(asset.read_bytes()).hexdigest()!=native['source']['sha256']:raise ValueError('DEF tile actual asset drift')
    import UnityPy
    objects={o.path_id:o for o in UnityPy.load(str(asset)).objects}
    rows=[(int(pid),r) for pid,r in native['components'].items() if r['native_class']=='BuffTile']
    if len(rows)!=1:raise ValueError('Exact DEF BuffTile ambiguous')
    pid,component=rows[0];data=objects[pid].read_typetree()
    if data!=component['raw']:raise ValueError('Actual DEF tile tree differs from pinned source')
    modifier=data['_buffs'][0]['attributes']['attributeModifiers'][0]
    if modifier!={'attributeType':2,'formulaItem':0,'value':0.0,'loadFromBlackboard':1,'fetchBaseValueFromSourceEntity':0}:raise ValueError('DEF source modifier requires new adapter')
    if data['_sourceSide']!=1 or data['_clearBuffsWhenLeft']!=1:raise ValueError('Source DEF tile membership changed')
    stage=source['stages']['level_main_03-08']['native_document'];tiles=[t for t in stage['mapData']['tiles'] if t['tileKey']=='tile_defup']
    from ark_sim.domains.tile_fields import board
    if not tiles or any(board(t)!={'def':200.0} for t in tiles):raise ValueError('Expected exact stage DEF200 blackboard')
    options=data['_targetOptions'];cfg={'_'+key:value for key,value in options.items()}
    cfg.update(_needProfessionMask=0,_forceIgnoreCamouflage=0)
    return {'schemaVersion':2,'manifest':{'id':'package/chapter03/defup_field','requires':['preset/ark_standard'],'metadata':{
        'source_locks':{'packages/campaign/chapter03_plans/source.plan.json':PIN,str(asset.resolve()):native['source']['sha256']},
        'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'actual_source_component_path_id':pid,
        'default_policy':'Virtual source side0 / ALLY1, category mask3, motion3; native switch fields preserved; owned child per occupied cell',
        'feedback_pending':['Native tile/actor getter and coordinate rounding calibration','Native maxStack child representation'],
        'client_verified':False}},
        'entities':[{'id':'unit/ch3/field/defup','kind':'entity','tags':['tile_field_owner'],'components':{
            'spatial':{},'selection_state':state(),'buffs':{'initial':['buff/ch3/defup_parent']}}}],
        'buffs':[{'id':'buff/ch3/defup_parent','kind':'buff','aura':{'selector':'selector/ch3/defup_members','buff':'buff/ch3/defup_child'}},
            {'id':'buff/ch3/defup_child','kind':'buff','stacking':{'mode':'independent'},'modifiers':[{'attribute':'def','layer':'flat','value':200.0}],
             'metadata':{'native_buff':deepcopy(data['_buffs'][0]),'source_blackboard':{'def':200.0}}}],
        'selectors':[{'id':'selector/ch3/defup_members','kind':'selector','region':{'type':'grid_offsets','offsets':[[0,0]],'rotate_with_facing':False},
            'filters':[{'state':'alive'}],'eligibility':{'rule':'rule/ch3/defup_qualification','parameters':{
                'source_configuration':cfg,'side_policy':'relative_ally_enemy','neutral_policy':'reject','defaults':state()}}}],
        'rules':[{'id':'rule/ch3/defup_qualification','kind':'rule','contract':'targeting.eligibility','implementation':{'type':'provider','provider':'model.targeting.eligibility'}}]}


if __name__=='__main__':
    import sys;sys.path.insert(0,str(ROOT));ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);ap.add_argument('--check',action='store_true');args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()))
    p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('DEF field model drift')
    else:OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'source_flat_DEF':200}))
