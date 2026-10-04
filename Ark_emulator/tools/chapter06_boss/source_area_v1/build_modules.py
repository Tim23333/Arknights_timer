"""Once per source-centred cast; selector is only the activation gate."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3]
BASES={'ordinary':('frstar2_v3','3d412e332107a889633292b6e824ea8607d8f532bdc0d53f5878448619a7a064','frstar2_v4'),'story':('frstar2_s_v2','798ca03a624b2f0167f965eaa5231de8a2282e3ee949559efd043756277cba86','frstar2_s_v3')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(which):
 old,pin,new=BASES[which];path=ROOT/'packages/campaign/chapter06_boss'/old/'model.json'
 if sha(path)!=pin:raise ValueError('Exact frozen source model required')
 p=json.loads(path.read_bytes());count=0
 for a in p['abilities']:
  for entry in a.get('timeline',[]):
   e=entry.get('effect',{})
   if e.get('op')=='area' and e.get('center')=='source':e['target']='source';count+=1
 if count!=(2 if which=='ordinary' else 1):raise ValueError('All sourcecentred Burst areas required')
 meta=p['manifest']['metadata'];meta['source_locks'][str(path.relative_to(ROOT))]=pin;meta['builder_sha256']=sha(Path(__file__));meta['reference_policies']['area_dispatch']='Source-centred nativeBurst resolves one area per cast, regardlessactivation selector gatecount. Explicittargetsource; allactualqualifiedmembers onepacket+oneCold. Source selector/capture/require_targets remain.'
 out=ROOT/'packages/campaign/chapter06_boss'/new;out.mkdir(exist_ok=True);dest=out/'model.json';dest.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());return dest
if __name__=='__main__':
 for which in BASES:
  p=build(which);print(json.dumps({'which':which,'path':str(p),'sha256':sha(p)}))
