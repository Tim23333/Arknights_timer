"""Bounded-memory read of actual CP4900; never emits another large journal."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'validation/campaign/chapter08_bsnake_full_actual_v1/terminal4900.checkpoint.json'
OUT=ROOT/'validation/campaign/chapter08_bsnake_terminal_prefix_audit_v2';OUT.mkdir(exist_ok=False)
def records(path):
 marker='"events":{"records":[';decoder=json.JSONDecoder()
 with path.open(encoding='utf8') as f:
  buffer=''
  while marker not in buffer:
   chunk=f.read(1024*1024)
   if not chunk:raise ValueError('Missing actual checkpoint event records')
   buffer=buffer[-len(marker):]+chunk
  position=buffer.index(marker)+len(marker)
  while True:
   while position<len(buffer) and buffer[position] in ', \r\n\t':position+=1
   if position<len(buffer) and buffer[position]==']':return
   try:row,end=decoder.raw_decode(buffer,position)
   except json.JSONDecodeError:
    chunk=f.read(1024*1024)
    if not chunk:raise ValueError('Truncated actual event record')
    buffer=buffer[position:]+chunk;position=0;continue
   yield row;position=end
count=0;summon=[];branches=[];activated=[];device_casts=[];costs=[];requests=[];transfers=[];rays=[]
for e in records(SOURCE):
 count+=1;assert e['id']==count
 kind=e['type'];p=e['payload']
 if kind=='ability.started' and p['ability']=='ability/ch8/bsnake/summon_flame':summon.append(e)
 if kind=='ability.started' and p['ability']=='ability/ch8/flame/explode':device_casts.append(e)
 if kind=='branch.phase_started':branches.append(e)
 if kind=='entity.activated':activated.append(e)
 if kind=='resource.changed' and p.get('resource')=='sp' and p.get('delta')==-25:costs.append(e)
 if kind=='timeline.finish_requested':requests.append(e)
 if kind=='timeline.source_transferred':transfers.append(e)
 if kind=='projectile.launched' and p.get('ability')=='ability/ch8/bsnake/firecommon':rays.append(e)
assert count==151580
assert summon and summon[0]['time']>=1047+2250
assert len(device_casts)==5 and len(costs)==5
assert len(activated)==5
assert [(e['time'],e['payload']['parameters']['track_source_at_next_wave']) for e in requests]==[(57,True),(4500,False)]
assert [(e['time'],e['payload']['source']) for e in transfers]==[(117,20)]
assert len(rays)==98
pin=json.loads(SOURCE.with_name('terminal4900.pin.json').read_bytes())
digest=hashlib.sha256()
with SOURCE.open('rb') as stream:
 while chunk:=stream.read(4*1024*1024):digest.update(chunk)
assert digest.hexdigest()==pin
report={'passed':True,'scope':'Actual immutable CP4900 event prefix only, not full140 or continuation/head. Streaming read retains selected numerical witnesses, no new large logs.','checkpoint_sha':pin,'event_count':count,'source_init75s_not_before':3297,'actual_summon':summon,'branches':branches,'actual_activated':activated,'actual_25SP_costs':costs,'actual_device_casts':device_casts,'source_requests':requests,'source_transfers':transfers,'ray_count_prefix':len(rays)}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(hashlib.sha256((OUT/'verification.json').read_bytes()).hexdigest())

