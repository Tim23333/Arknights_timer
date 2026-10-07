"""Exact typed independent source-plan review, never imports simulation runtime."""
import hashlib,json,re,sys,traceback
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.build_mainline_dependencies import resolve_enemy,DEFAULT_DB,PIN
PLAN=ROOT/'packages/campaign/chapter11_source_prepare/source.plan.v1.json'
EXPECTED='db510b260c64266315fd22ea2a5f2708434089d4be4272e9afb4c7dc148c6518'
OUT=ROOT/'validation/campaign/chapter11_source_prepare/source.plan.review.v1.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def equal(a,b,path='root'):
    if type(a)is not type(b):raise ValueError('Source type changed at '+path+': '+type(a).__name__+'/'+type(b).__name__)
    if isinstance(a,dict):
        if set(a)!=set(b):raise ValueError('Source keyset changed at '+path)
        for k in a:equal(a[k],b[k],path+'.'+k)
    elif isinstance(a,list):
        if len(a)!=len(b):raise ValueError('Source list length changed at '+path)
        for i,(x,y) in enumerate(zip(a,b)):equal(x,y,path+'['+str(i)+']')
    elif a!=b:raise ValueError('Source value changed at '+path)
def main():
    assert sha(PLAN)==EXPECTED;p=json.loads(PLAN.read_bytes());assert p['fixed_commit']==PIN and p['chapter']==11
    assert all(sha(k)==h for k,h in p['source_locks'].items())
    table=json.loads(Path(p['stage_table_identity']['path']).read_bytes())['stages']
    candidates={k:v for k,v in table.items() if re.fullmatch(r'main_11-\d+',k) and v.get('levelId') and v['difficulty']=='NORMAL'}
    last=sorted(candidates,key=lambda k:int(k.rsplit('-',1)[1]))[-2:]
    assert last==['main_11-17','main_11-18'] and [r['native_id'] for r in p['targets']]==last
    assert [r['display_code'] for r in p['targets']]==['11-19','11-20']
    db=json.loads(DEFAULT_DB.read_bytes());report={};branch_dependencies=[]
    for target in p['targets']:
        equal(target['fixed_stage_row'],candidates[target['native_id']],'fixed_table.'+target['native_id'])
        level=target['level_asset'];s=p['stages'][level];native=json.loads((ROOT/'packages/campaign/native_reference'/(level+'.json')).read_bytes())
        equal(s['native_document'],native,level+'.native_document');equal(s['options'],native['options'],level+'.options')
        equal(s['features']['branches_preserved'],native.get('branches'),level+'.branches')
        refs=s['variant_ids'];assert len(refs)==len(native['enemyDbRefs'])
        for ref,vid in zip(native['enemyDbRefs'],refs):
            equal(p['variants'][vid]['native_reference'],ref,vid+'.reference');equal(p['variants'][vid]['native_enemy'],resolve_enemy(db,ref),vid+'.DB')
        raw_actions=[{'wave':wi,'fragment':fi,'action':ai,'native':a} for wi,w in enumerate(native['waves']) for fi,f in enumerate(w['fragments']) for ai,a in enumerate(f['actions'])]
        assert len(raw_actions)==len(s['actions'])
        for raw,stored in zip(raw_actions,s['actions']):equal(raw,{k:stored[k] for k in raw},level+'.actions')
        births=Counter();controls=Counter()
        for a in raw_actions:
            v=a['native'];(births if v['actionType']=='SPAWN' else controls)[v['key'] if v['actionType']=='SPAWN' else v['actionType']]+=v['count']
        assert sum(births.values())==s['features']['spawn_count'];equal(dict(births),s['features']['spawn_by_key']);equal(dict(controls),s['features']['control_actions'])
        tokens=[{'bucket':bucket,'index':i,'native_record':r} for bucket,values in native['predefines'].items() for i,r in enumerate(values or [])]
        equal(tokens,s['predefine_records'],level+'.typed_predefines')
        for bucket,value in native['predefines'].items():
            assert type(value)in (list,dict) and (type(value)is list or not value),'Unexpected nonempty native bucket '+bucket
        branch_births=Counter()
        for branch,body in (native.get('branches') or {}).items():
            for phase in body['phases']:
                for a in phase['actions']:
                    if a['actionType']=='SPAWN':
                        branch_births[a['key']]+=a['count']
                        if not any(p['variants'][vid]['native_enemy']['native_id']==a['key'] for vid in refs):branch_dependencies.append({'stage':level,'branch':branch,'native_action':a,'key':a['key'],'selected_DB_level':None,'status':'branch_literal_missing_from_native_enemyDbRefs'})
        report[level]={'display':target['display_code'],'wave_born':sum(births.values()),'branch_spawn_declarations':dict(branch_births),'controls':dict(controls),
          'native_options':native['options'],'typed_predefine_counts':{k:len(v) for k,v in native['predefines'].items()},
          'native_predefine_bucket_types':{k:type(v).__name__ for k,v in native['predefines'].items()},
          'NPC_null_alias_count':sum(r['alias'] is None for r in native['predefines']['characterInsts']),
          'runes_type':type(native.get('runes')).__name__,'optional_runes_type':type(native.get('optionalRunes')).__name__,
          'global_buffs_type':type(native.get('globalBuffs')).__name__,'all_native_routes_preserved':True,'all_native_actions_typed_exact':True}
    a=report['level_main_11-17'];assert a['wave_born']==10 and a['native_options']['isTrainingLevel'] is True
    assert a['typed_predefine_counts']=={'characterInsts':4,'tokenInsts':3,'characterCards':0,'tokenCards':1}
    assert a['controls']=={'STORY':4,'ACTIVATE_PREDEFINED':2,'PLAY_BGM':1} and a['NPC_null_alias_count']==4
    assert report['level_main_11-18']['wave_born']==35 and len(p['variants'])==9
    assert all(sha(k)==h for k,h in p['source_locks'].items()) and sha(PLAN)==EXPECTED
    result={'schema':'ark-sim/chapter11-plan-independent-static-review/v1','passed':True,'plan_sha256':EXPECTED,'variant_count':9,
      'stages':report,'branch_only_dependencies':branch_dependencies,'scope':'Fixed56 selected source inventory and lossless typed native data only; branch DB level requires separate source resolution, no inferred level0.',
      'source_guard_current':True,'reviewer_sha256':sha(__file__),'runtime_created':False,'simulation_started':False,'whole_stage_approved':False,'client_verified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'review_sha256':sha(OUT),'variants':9,'branch_only_dependencies':len(branch_dependencies),'runtime':False}))
if __name__=='__main__':
    try:main()
    except Exception as error:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.with_name('source.plan.review.failure.v1.json').write_text(json.dumps({'passed':False,'error':str(error),'traceback':traceback.format_exc(),'runtime_created':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        raise
