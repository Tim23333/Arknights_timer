import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/chapter08_jt82_nested_locks_peer_v1';OUT.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();P=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v5.json';p=json.loads(P.read_bytes());locks={};origins={};nonfile=[]
def walk(value,origin):
 if isinstance(value,dict):
  for key,item in value.items():
   if key=='source_locks' and isinstance(item,dict):
    for name,pin in item.items():
     if isinstance(pin,str) and len(pin)==64:
      file=Path(name)
      if not file.is_absolute():file=ROOT/file
      if not file.is_file():nonfile.append({'origin':origin,'key':name,'pin':pin});continue
      if str(file) in locks:assert locks[str(file)]==pin
      locks[str(file)]=pin;origins.setdefault(str(file),[]).append(origin)
   else:walk(item,origin)
 elif isinstance(value,list):
  for item in value:walk(item,origin)
for name in p['manifest']['metadata']['source_locks']:
 file=Path(name);assert sha(file)==p['manifest']['metadata']['source_locks'][name];walk(json.loads(file.read_bytes()),str(file))
before={name:sha(Path(name)) for name in locks};assert all(before[name]==pin for name,pin in locks.items())
after={name:sha(Path(name)) for name in locks};assert before==after
report={'passed':True,'package_sha':sha(P),'nested_file_pins':len(locks),'declared_locks':locks,'guards_start':before,'guards_end':after,'guards_equal':True,'origins':origins,'declared_nonfile_identifiers':nonfile,'scope':'Supplemental read-only recursive source_locks declared inside each currentstage source module, all actualexisting file pins compared. Nonfile identifiers separately listed rather than silently claimed as fileguard. No runtime/whole or oldfreeze rewrite.'};(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'sha':sha(OUT/'verification.json'),'nested_files':len(locks),'nonfile':len(nonfile)}))
