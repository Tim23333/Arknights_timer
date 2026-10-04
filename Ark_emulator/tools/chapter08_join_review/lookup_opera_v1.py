"""Offline OperaConfig ScriptableObject search, never V1 combat import."""
import json,hashlib
from pathlib import Path
import UnityPy
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'packages/campaign/chapter08_stage_controls/source/opera.local_search.v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    records=[];matches=[];errors=[]
    paths=[p for p in (ROOT.parent/'data/anon').glob('*/CAB-*') if not p.name.endswith('.resS')]
    for index,path in enumerate(paths):
        count=0
        try:
            env=UnityPy.load(str(path))
            for obj in env.objects:
                if obj.type.name!='MonoBehaviour':continue
                count+=1
                try:raw=obj.read_typetree()
                except Exception as e:errors.append({'path':str(path),'path_id':obj.path_id,'error':str(e)[:180]});continue
                name=raw.get('m_Name','');text=json.dumps(raw,ensure_ascii=False)
                if 'blast_effect_x' in text or 'blast_effect_y' in text or name=='main_08-17' and '_commands' in raw:
                    matches.append({'path':str(path),'sha256':sha(path),'path_id':obj.path_id,'type':obj.type.name,'raw':raw})
            records.append({'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'MonoBehaviour_count':count})
        except Exception as e:errors.append({'path':str(path),'error':str(e)[:180]})
        if index%20==0:print(index,len(matches),flush=True)
    assert not OUT.exists();OUT.write_bytes((json.dumps({'scope':'All171 available anonymous CAB MonoBehaviours/ScriptableObjects, original battle GameObject search had no roots. Absence from this inventory is not absence from actual client or purevisual proof.','records':records,'matches':matches,'errors':errors},ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(OUT),'matches':len(matches),'errors':len(errors)}))
if __name__=='__main__':main()
