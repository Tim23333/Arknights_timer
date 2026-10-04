"""Finite offline FB→BSON→referenced-Buff closure; never import V1 combat."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'ark_parser/enemy'))
from extract_enemy_data import FB
from tools.chapter06.cold.decode_source import FIELDS,attrs
from tools.build_chapter01_enemy_sources import bson_source
PATH=ROOT.parent/'data/anon_textassets/buff_table352282.dat'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def index_rows(f):
 result={}
 for slot in f.vector(f.target_of(f.table_fields(f.root)[0])):
  entry=f.target_of(slot);pair=f.table_fields(entry);key=f.read_string(f.target_of(pair[0]));result[key]=(entry,f.target_of(pair[1]))
 return result
def decode(f,entry,pos):
 fs=f.table_fields(pos);decoded={}
 for i,(name,kind) in enumerate(FIELDS):
  off=fs[i] if i<len(fs) else None
  if off is None:value=False if kind=='bool' else None if kind=='str' else {} if kind=='attributes' else 0
  elif kind=='attributes':
   apos=f.target_of(off);af=f.table_fields(apos);value=attrs(f,apos) if af else {'raw_empty_table':True,'row_offset':apos,'field_offsets':[]}
  elif kind=='str':value=f.read_string(f.target_of(off))
  elif kind=='bool':
   if f.d[off] not in (0,1):raise ValueError('Invalid packed source Boolean')
   value=f.d[off]==1
  elif kind=='byte':value=f.d[off]
  else:value=getattr(f,kind)(off)
  decoded[name]={'field_index':i,'offset':off,'value':value,'schema_default_when_offset_absent':off is None}
 return {'entry_offset':entry,'row_offset':pos,'field_offsets':fs,'decoded':decoded,'unknown_extra_field_offsets':fs[len(FIELDS):]}
def buff_refs(v):
 found=set()
 if isinstance(v,dict):
  for k,x in v.items():
   if k in ('_buffKey','buffKey','_ownerBuffKey','_targetBuffKey') and isinstance(x,str) and x:found.add(x)
   if k in ('_buffKeys','buffKeys') and isinstance(x,list):found.update(i for i in x if isinstance(i,str) and i)
   found.update(buff_refs(x))
 elif isinstance(v,list):
  for x in v:found.update(buff_refs(x))
 return found
def closure(seeds):
 f=FB(PATH);index=index_rows(f);pending=list(seeds);rows={};missing=[];templates={};edges=[];bson_identity=None
 while pending:
  key=pending.pop(0)
  if key in rows or key in missing:continue
  if key not in index:missing.append(key);continue
  row=decode(f,*index[key]);rows[key]=row;template=row['decoded']['templateKey']['value']
  if not template:continue
  b=bson_source({template});bson_identity={'source':b['source'],'payload_sha256':b['payload_sha256']}
  if template not in b['templates']:templates[template]={'missing':True};continue
  document=b['templates'][template];templates[template]=document
  for child in sorted(buff_refs(document['parsed'])):
   edges.append({'parent_buff':key,'template':template,'referenced_buff':child});pending.append(child)
 return {'schema':'ark-sim/recursive-buff-source/v1','roots':list(seeds),'FB_source':{'path':str(PATH),'sha256':sha(PATH),'bytes':PATH.stat().st_size},'field_schema':FIELDS,'schema_policy':'Existing calibrated34-slot BuffData schema only; unknown extra offsets retained, never inferred as typed parameters. Missing offset means schema default, not a separately defined explicit source value.','rows':rows,'missing_rows':sorted(missing),'BSON_source':bson_identity,'templates':templates,'edges':edges,'method_bodies_verified':False,'runtime_authored':False,'offline_only':True,'builder_sha256':sha(Path(__file__))}
def main():
 out=ROOT/'packages/campaign/chapter08_consumers/special/dragon_fire.supplement.v1.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();result=closure(['dragon_fire']);out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'rows':list(result['rows']),'missing':result['missing_rows'],'templates':list(result['templates'])}))
if __name__=='__main__':main()
