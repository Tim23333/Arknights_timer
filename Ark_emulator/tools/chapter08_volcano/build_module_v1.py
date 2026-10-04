"""Exact Chapter8 volcano operands using verified generic periodic fields."""
import json,hashlib,sys
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
SOURCE=ROOT/'packages/campaign/chapter08_source_prepare/integration/environment.native.v1.json'
PARENT=ROOT/'packages/campaign/chapter04_environment/volcano.reference_module.json'
OUT=ROOT/'packages/campaign/chapter08_consumers/environment/volcano.module.v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    assert sha(SOURCE)=='c813f7c2308c2308baaa19a88a3e18305db7a18d1404f6a7f1351b018296d976'
    s=json.loads(SOURCE.read_bytes());oldsource=ROOT/'packages/campaign/chapter04_environment/source.reference.json'
    a=json.loads(oldsource.read_bytes())['prefabs']['tile_volcano'];b=s['prefabs']['tile_volcano']
    assert a['source']==b['source']
    assert {k:v['raw'] for k,v in a['components'].items()}=={k:v['raw'] for k,v in b['components'].items()}
    assert a['geometry_sources']==b['geometry_sources']
    p=json.loads(PARENT.read_bytes());tr=next(c['raw'] for c in b['components'].values() if c['native_class']=='UniformRandomTrigger');cr=next(c['raw'] for c in b['components'].values() if c['native_class']=='CastTile')
    node=json.loads(cr['_actions']['SerializedState'])[0];assert node['_damageType']=='PURE' and node['_attackType']=='NONE' and node['_ignoreForSp'] is False
    operands=[t for t in s['stage_tile_operands']['level_main_08-16'] if t['tileKey']=='tile_volcano'];expected={'damage':1000.0,'cd_min':8.0,'cd_max':12.0}
    assert len(operands)==6 and all({v['key']:v['value'] for v in t['blackboard']}==expected for t in operands)
    p['manifest']['id']='package/ch8/volcano/source_v1';meta=p['manifest']['metadata'];meta['source_locks']={str(x):sha(x) for x in (SOURCE,oldsource,PARENT,Path(__file__))}
    meta['exact_shared_prefab_verified']=True;meta['chapter8_source_operands']=operands;meta['source_geometry']=deepcopy(b['geometry_sources'])
    meta['source_action']=node;meta['source_trigger']=tr;meta['source_cast']=cr;meta['source_fields']=6
    meta['model_policies']['visibility']='Source respectTargetFree0 means respect targetFree, inherited explicit noSource default availability/camo exclusion9/17 reference; source nativecast selection bits retained.'
    meta['scope']='Six native Chapter8 source cells damage1000/random8..12. Generic cell pluscombat orthogonal neighbour reference preserves literal radii1.710000038/.709999978 mismatch. No complete-stage approval.'
    profile=meta['tile_profiles']['tile_volcano'];profile['expected_blackboard']=expected
    profile['origin']['source_sha256']=sha(SOURCE);profile['effects'][0]['fixed_amount']=1000
    text=json.dumps(p,ensure_ascii=False);text=text.replace('rule/ch4/volcano','rule/ch8/volcano');p=json.loads(text)
    return p

if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'source_fields':6,'newcore':False}))
