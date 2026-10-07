"""Independent typed12-17 future source inventories, no runtime or defaults."""
import copy,hashlib,json,re,sys,traceback
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter11_source_prepare.review_plan import equal
from tools.build_mainline_dependencies import DEFAULT_DB,PIN,resolve_enemy
OUT=ROOT/'validation/campaign/chapter11_source_prepare/future.plans.review.v1.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def projection(raw,path='$',undefined=None):
    undefined={} if undefined is None else undefined
    if isinstance(raw,dict) and set(raw)=={'m_defined','m_value'}:
        if type(raw['m_defined'])is not bool:raise ValueError('Nonboolean source definition flag')
        if not raw['m_defined']:undefined[path]=copy.deepcopy(raw);return (False,None,undefined)
        return projection(raw['m_value'],path,undefined)
    if isinstance(raw,dict):
        result={}
        for k,v in raw.items():
            included,value,_=projection(v,path+'.'+k,undefined)
            if included:result[k]=value
        return True,result,undefined
    if isinstance(raw,list):
        result=[]
        for i,v in enumerate(raw):
            included,value,_=projection(v,path+'['+str(i)+']',undefined)
            if not included:raise ValueError('Undefined source list member requires schema')
            result.append(value)
        return True,result,undefined
    return True,copy.deepcopy(raw),undefined
def main():
    db=json.loads(DEFAULT_DB.read_bytes());rows=[];guards={str(DEFAULT_DB):sha(DEFAULT_DB)}
    for chapter in range(12,18):
        path=ROOT/('packages/campaign/chapter'+str(chapter)+'_source_prepare')/('source.plan.v2.json' if chapter==17 else 'source.plan.v1.json')
        p=json.loads(path.read_bytes());assert p['fixed_commit']==PIN and p['chapter']==chapter
        guards[str(path)]=sha(path);assert all(sha(k)==h for k,h in p['source_locks'].items());guards.update(p['source_locks'])
        table=json.loads(Path(p['stage_table_identity']['path']).read_bytes())['stages']
        normal={k:v for k,v in table.items() if re.fullmatch(r'main_'+str(chapter)+r'-\d+',k) and v.get('levelId') and v.get('difficulty')=='NORMAL'}
        last=sorted(normal,key=lambda k:int(k.rsplit('-',1)[1]))[-2:];assert last==[r['native_id'] for r in p['targets']]
        facts=[];inline=0
        for target in p['targets']:
            equal(target['fixed_stage_row'],normal[target['native_id']]);name=target['level_asset'];s=p['stages'][name]
            original=ROOT/'packages/campaign/native_reference'/(name+'.json');native=json.loads(original.read_bytes());guards[str(original)]=sha(original)
            equal(s['native_document'],native,name+'.full_typed_document');equal(s['options'],native['options'],name+'.options')
            assert len(s['variant_ids'])==len(native['enemyDbRefs'])
            for ref,vid in zip(native['enemyDbRefs'],s['variant_ids']):
                saved=p['variants'][vid];equal(saved['native_reference'],ref,vid+'.ref')
                if ref['useDb'] is True:equal(saved['native_enemy'],resolve_enemy(db,ref),vid+'.DB')
                else:
                    assert ref['useDb'] is False;included,defined,undefined=projection(ref['overwrittenData']);actual=saved['native_enemy']
                    equal(actual['raw_inline'],ref['overwrittenData'],vid+'.raw_inline');equal(actual['resolved'],defined,vid+'.defined_only')
                    equal(actual['undefined_native_fields'],undefined,vid+'.undefined_wrappers')
                    assert actual['database_inheritance_applied'] is False and actual['native_defaults_resolved'] is False and actual['runtime_conversion_approved'] is False
                    inline+=1
            flat=[{'wave':wi,'fragment':fi,'action':ai,'native':a} for wi,w in enumerate(native['waves']) for fi,f in enumerate(w['fragments']) for ai,a in enumerate(f['actions'])]
            assert len(flat)==len(s['actions']);born=Counter()
            for raw,record in zip(flat,s['actions']):
                equal(raw,{k:record[k] for k in raw},name+'.actions')
                if raw['native']['actionType']=='SPAWN':born[raw['native']['key']]+=raw['native']['count']
            assert sum(born.values())==s['features']['spawn_count'];equal(dict(born),s['features']['spawn_by_key'])
            facts.append({'display_code':target['display_code'],'native_id':target['native_id'],'wave_born':sum(born.values()),
              'options':native['options'],'branches_typed_preserved':True,'predefine_bucket_types':{k:type(v).__name__ for k,v in native['predefines'].items()},'native_runes_type':type(native.get('runes')).__name__})
        assert inline==4 if chapter==17 else inline==0
        if chapter==17:assert len(p['variants'])==16 and [r['wave_born'] for r in facts]==[64,43]
        rows.append({'chapter':chapter,'plan_path':path.relative_to(ROOT).as_posix(),'plan_sha256':sha(path),'variants':len(p['variants']),'inline_reference_uses':inline,'stages':facts,'passed':True,'runtime_created':False})
    # Explicitly challenge the reusable inline resolver with falsey declared
    # values and undefined wrappers using an independent expected projection.
    from tools.chapter_source_inventory_v1.build_v2 import source_enemy
    ref={'id':'peer_inline_source','level':3,'useDb':False,'overwrittenData':{
      'prefabKey':{'m_defined':True,'m_value':'peer_exact_prefab'},'attributes':{'maxHp':{'m_defined':True,'m_value':0}},
      'zero':{'m_defined':True,'m_value':0},'bool':{'m_defined':True,'m_value':False},'null':{'m_defined':True,'m_value':None},
      'empty':{'m_defined':True,'m_value':{}},'unknown':{'m_defined':False,'m_value':123456}}}
    got=source_enemy({'peer_inline_source':'must_not_inherit'},ref);_,expected,undefined=projection(ref['overwrittenData'])
    equal(got['resolved'],expected);equal(got['undefined_native_fields'],undefined)
    assert got['database_inheritance_applied'] is False and 'unknown' not in got['resolved']
    bad=copy.deepcopy(ref);bad['overwrittenData']['unknown']['m_defined']=0
    try:source_enemy({},bad)
    except ValueError:pass
    else:raise AssertionError('Integer0 accepted as native definition boolean')
    assert all(sha(p)==h for p,h in guards.items())
    result={'schema':'ark-sim/future-source-plan-independent-review/v1','passed':True,'plans':rows,'source_guards':guards,'source_current':True,
      'inline_falsey_values_types_preserved':True,'undefined_fields_not_unwrapped_or_DB_inherited':True,'integer_definition_flag_rejected':True,
      'runtime_created':False,'simulation_started':False,'whole_stage_count_changed':False,'reviewer_sha256':sha(__file__)}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'chapters':6,'sha256':sha(OUT),'runtime':False}))
if __name__=='__main__':
    try:main()
    except Exception as error:
        OUT.parent.mkdir(parents=True,exist_ok=True);OUT.with_name('future.plans.review.failure.v1.json').write_text(json.dumps({'passed':False,'error':str(error),'traceback':traceback.format_exc(),'runtime_created':False},indent=2)+'\n',encoding='utf8');raise
