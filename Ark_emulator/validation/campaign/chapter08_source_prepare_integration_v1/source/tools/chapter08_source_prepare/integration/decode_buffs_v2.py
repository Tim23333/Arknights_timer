"""Typed offline FB rows for actual Chapter7 loadFromDB refs; no V1 combat imports."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'ark_parser/enemy'))
from extract_enemy_data import FB
from tools.chapter06.cold.decode_source import FIELDS,attrs
PATH=ROOT.parent/'data/anon_textassets/buff_table352282.dat';OUT=ROOT/'packages/campaign/chapter08_source_prepare/integration/buffs.typed.v2.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 paths=[ROOT/'packages/campaign/chapter08_source_prepare/integration/enemies.native.v1.json',ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v1.json',ROOT/'packages/campaign/chapter08_source_prepare/integration/environment.native.v1.json'];keys=set()
 def scan(v):
  if isinstance(v,dict):
   if v.get('buffKey'):keys.add(v['buffKey'])
   for x in v.values():scan(x)
  elif isinstance(v,list):
   for x in v:scan(x)
 for p in paths:scan(json.loads(p.read_bytes()))
 f=FB(PATH);rows={}
 for slot in f.vector(f.target_of(f.table_fields(f.root)[0])):
  entry=f.target_of(slot);pair=f.table_fields(entry);key=f.read_string(f.target_of(pair[0]))
  if key not in keys:continue
  pos=f.target_of(pair[1]);fs=f.table_fields(pos);decoded={}
  for i,(name,kind) in enumerate(FIELDS):
   off=fs[i] if i<len(fs) else None
   if off is None:value=False if kind=='bool' else None if kind=='str' else {} if kind=='attributes' else 0
   elif kind=='attributes':
    apos=f.target_of(off);af=f.table_fields(apos)
    value=attrs(f,apos) if af else {'abnormalFlags':[],'attributeModifiers':[],'field_offsets':[],'raw_empty_table':True,'row_offset':apos}
   elif kind=='str':value=f.read_string(f.target_of(off))
   elif kind=='bool':
    if f.d[off] not in (0,1):raise ValueError('Invalid packed boolean source')
    value=f.d[off]==1
   elif kind=='byte':value=f.d[off]
   else:value=getattr(f,kind)(off)
   decoded[name]={'field_index':i,'offset':off,'value':value}
  rows[key]={'entry_offset':entry,'row_offset':pos,'field_offsets':fs,'decoded':decoded,'unknown_extra_field_offsets':fs[len(FIELDS):]}
 result={'schema':'ark-sim/chapter08-buff-typed-source/v1','source':{'path':str(PATH.resolve()),'sha256':sha(PATH),'bytes':PATH.stat().st_size},'reference_policy':'All inline buffKey IDs are queried as additional table evidence; native loadFromDB0 remains inline and is never changed into DB lookup. Missing table rows for inline definitions are source differences/pending, not guessed empty Buffs.','required_keys':sorted(keys),'found_rows':rows,'missing_keys':sorted(keys-set(rows)),'field_schema':FIELDS,'schema_policy':'Older 34-slot BuffData schema calibrated by existing Cold/Frozen evidence. Extra field offsets remain untyped/pending; no later schema alignment asserted.','reference_inputs':{str(p):sha(p) for p in paths},'offline_reader_only_no_V1_combat':True,'builder_sha':sha(Path(__file__)),'reader_sha':sha(ROOT.parent/'ark_parser/enemy/extract_enemy_data.py'),'schema_helper_sha':sha(ROOT/'tools/chapter06/cold/decode_source.py'),'runtime_authored':False,'client_verified':False};assert not OUT.exists();OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'required':len(keys),'found':len(rows),'missing':result['missing_keys']}))
if __name__=='__main__':main()
