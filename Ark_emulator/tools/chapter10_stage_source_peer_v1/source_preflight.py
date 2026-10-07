"""Independent lossless source preflight; assembled package approval pending."""
import json,hashlib,math,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
PLAN=ROOT/'packages/campaign/chapter10_source_prepare/source.plan.v1.json'
OUT=ROOT/'validation/campaign/chapter10_stage_source_peer_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def exact(a,b,path='$'):
    if type(a)!=type(b):raise AssertionError((path,type(a).__name__,type(b).__name__,a,b))
    if isinstance(a,dict):
        assert set(a)==set(b),(path,'keys',set(a)^set(b))
        for k in a:exact(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        assert len(a)==len(b),(path,'length',len(a),len(b))
        for i,(x,y) in enumerate(zip(a,b)):exact(x,y,path+'['+str(i)+']')
    else:assert a==b,(path,a,b)
def leaf_types(value,path='$',answer=None):
    if answer is None:answer={}
    if isinstance(value,dict):
        if not value:answer[path]='empty_object'
        for k,v in value.items():leaf_types(v,path+'.'+k,answer)
    elif isinstance(value,list):
        if not value:answer[path]='empty_array'
        for i,v in enumerate(value):leaf_types(v,path+'['+str(i)+']',answer)
    else:
        if type(value) is float:assert math.isfinite(value),path
        answer[path]=type(value).__name__
    return answer
def expected_route(route,rows):
    result=json.loads(json.dumps(route))
    for p in [result['startPosition'],result['endPosition'],*[c['position'] for c in result['checkpoints'] or []]]:p['row']=rows-1-p['row']
    # Source strings remain valid V2 enums; conversion to documented integers
    # can be certified separately without discarding unknown route fields.
    return result
def source():
    data=json.loads(PLAN.read_bytes());target=next(t for t in data['targets'] if t['native_id']=='main_10-14')
    tablepath=ROOT/'packages/campaign/chapter10_source_prepare/stage_table.fixed56.source.json';table=json.loads(tablepath.read_bytes())['stages']
    normal=sorted([k for k,v in table.items() if re.fullmatch('main_10-[0-9]+',k) and v['difficulty']=='NORMAL' and v.get('levelId')],key=lambda x:int(x.rsplit('-',1)[1]))[-2:]
    assert normal==['main_10-14','main_10-15'] and target['display_code']=='10-16' and target['difficulty']=='NORMAL'
    exact(target['fixed_stage_row'],table['main_10-14'])
    stage=data['stages']['level_main_10-14'];native=stage['native_document'];assert digest(native)==stage['native_document_digest']
    source_matches={p:sha(Path(p))==h for p,h in data['source_locks'].items()};assert all(source_matches.values()),source_matches
    actions=[a for w in native['waves'] for f in w['fragments'] for a in f['actions']];spawn=[a for a in actions if a['actionType']=='SPAWN'];control=[a for a in actions if a['actionType']!='SPAWN'];used=sorted({a['routeIndex'] for a in spawn})
    assert len(native['routes'])==30 and len(used)==28 and sum(a['count'] for a in spawn)==32
    assert Counter(a['actionType'] for a in control)=={'DISPLAY_ENEMY_INFO':2}
    options=native['options'];assert options['initialCost']==10 and options['characterLimit']==8 and options['maxLifePoint']==3 and options['moveMultiplier']==.5
    assert type(options['steeringEnabled']) is bool and options['steeringEnabled']
    checkpoints=[c for index in used for c in native['routes'][index]['checkpoints'] or []]
    kinds=Counter(c['type'] for c in checkpoints);assert kinds=={'MOVE':170,'WAIT_FOR_SECONDS':20,'DISAPPEAR':8,'APPEAR_AT_POS':8}
    waiting=Counter(c['time'] for c in checkpoints if c['type']=='WAIT_FOR_SECONDS');assert waiting[50.0]==2 and waiting[100.0]==2
    pairs=[]
    for index in used:
        row=native['routes'][index];assert type(row['allowDiagonalMove']) is bool
        hidden=None
        for ci,c in enumerate(row['checkpoints'] or []):
            if c['type']=='DISAPPEAR':assert hidden is None;hidden=ci
            elif c['type']=='APPEAR_AT_POS':assert hidden is not None;pairs.append({'route':index,'disappear_checkpoint':hidden,'appear_checkpoint':ci,'appear_position':c['position']});hidden=None
        assert hidden is None
    assert len(pairs)==8
    pre=native['predefines'];assert type(pre['characterInsts']) is dict and not pre['characterInsts'] and len(pre['tokenInsts'])==1
    token=pre['tokenInsts'][0];assert token['inst']['potentialRank']==0 and token['position']=={'row':0,'col':0} and token['inst']['characterKey']=='trap_058_gunctrl'
    rows=len(native['mapData']['map']);cols=len(native['mapData']['map'][0]);assert (rows,cols)==(9,13)
    assert all(r['difficultyMask']=='EASY' for r in native['runes'])
    return {'stage':target['native_id'],'display':target['display_code'],'native_document_sha256':digest(native),'options':options,'births_by_source_key':dict(Counter({key:sum(a['count'] for a in spawn if a['key']==key) for key in {a['key'] for a in spawn}})),'source_spawn_actions':len(spawn),'native_control_actions':control,'native_waves':len(native['waves']),'routes':30,'used_routes':used,'checkpoint_kinds':dict(kinds),'wait_seconds_counts':dict(waiting),'hidden_pairs':pairs,'map_size':[rows,cols],'tile_keys':dict(Counter(native['mapData']['tiles'][i]['tileKey'] for row in native['mapData']['map'] for i in row)),'token_source':token,'token_runtime_expected_position':{'row':rows-1-token['position']['row'],'col':token['position']['col']},'runes_preserved_inactive':native['runes'],'branches':native['branches'],'typed_leaf_inventory':leaf_types(native),'source_locks_current':source_matches,'expected_route_conversions':[expected_route(r,rows) for r in native['routes']]}
def main():
    report={'schema':'ark-sim/stage-source-static-preflight/v1','source':{'path':str(PLAN),'sha256':sha(PLAN)},'source_preflight':source(),'assembled_package_checked':False,'assembled_package_approved':False,'simulation_executed':False,'pending':['Root final frozen package SHA and source/definition replacement manifest','Actual scenario fields and all native route/action conversions','Fixed12 original attributes/owned skills/summons against source baseline, only base life99999 override allowed']}
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'source.preflight.v1.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'source_preflight':True,'assembled_package_approved':False,'path':str(path),'sha256':sha(path)}))
if __name__=='__main__':main()
