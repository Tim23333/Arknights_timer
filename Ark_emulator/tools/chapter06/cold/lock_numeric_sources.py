"""Lock source duration and TARGETFROZEN scale values by exact native row paths."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[3]
NATIVE=ROOT/'packages/campaign/chapter06_sources/native.reference.json'
OUT=ROOT/'packages/campaign/chapter06_cold/numeric.sources.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    data=json.loads(NATIVE.read_bytes());values=[]
    for key,row in data['variants'].items():
        resolved=row['native_enemy']['resolved']
        for index,bb in enumerate(resolved.get('talentBlackboard') or []):
            if bb['key'] in ('attackfreeze.freeze','boom.freeze','atkup.atk_scale'):
                values.append({'path':['variants',key,'native_enemy','resolved','talentBlackboard',index],'source_variant':key,**bb})
        for index,skill in enumerate(resolved.get('skills') or []):
            for n,bb in enumerate(skill.get('blackboard') or []):
                if bb['key']=='freeze':values.append({'path':['variants',key,'native_enemy','resolved','skills',index,'blackboard',n],'source_variant':key,'source_skill':skill.get('prefabKey'),**bb})
    assert {v['value'] for v in values if v['key'].endswith('freeze')}=={5.0,10.0}
    assert {v['value'] for v in values if v['key']=='atkup.atk_scale'}=={1.5,2.5}
    if len(values)!=10:raise ValueError('Exact selected source value closure differs')
    return {'schema':'ark-sim/chapter06-cold-numeric-source/v1','native_reference':{'path':str(NATIVE),'sha256':sha(NATIVE)},'source_locks':data['source_locks'],'values':values,'builder_sha256':sha(Path(__file__)),'runtime_binding':'Exact source5/10 incoming duration and source1.5/2.5 target-frozen policy parameters; no ordinary enemy module claim'}
if __name__=='__main__':
    OUT.write_bytes((json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'sha256':sha(OUT)}))
