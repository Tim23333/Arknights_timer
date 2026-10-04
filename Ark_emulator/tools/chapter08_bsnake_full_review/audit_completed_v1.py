"""Independent source oracle, only consumes this review's actual capture."""
import json,hashlib
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ACT=ROOT/'validation/campaign/chapter08_bsnake_full_actual_v1'
OUT=ROOT/'validation/campaign/chapter08_bsnake_full_source_audit_v1';OUT.mkdir(exist_ok=False)
raw=(ACT/'forward.capture.json').read_bytes();capture=json.loads(raw);events=capture['events']
boss=20;fire='ability/ch8/bsnake/firecommon';summon='ability/ch8/bsnake/summon_flame'
def rows(kind):return [e for e in events if e['type']==kind]
volleys=[e for e in rows('source.bsnake.screen.volley')]
assert [e['time'] for e in volleys]==[207+60*n for n in range(1,11)]+[4650+60*n for n in range(1,11)]
rays=[e for e in rows('projectile.launched') if e['payload']['source']==boss and e['payload']['ability']==fire]
assert len(rays)==140
assert len([e for e in rays if e['time']<1047])==70
assert len([e for e in rays if e['time']>=4650])==70
assert len(Counter(e['payload']['definition'] for e in rays))==7
assert all(v==20 for v in Counter(e['payload']['definition'] for e in rays).values())
hits=[e for e in rows('damage.accepted') if e['payload']['source']==boss and e['payload']['ability']==fire]
assert len(hits)==140
for target,res in zip(range(13,20),[17,37,53,73,17,37,53]):
 actual=[e for e in hits if e['payload']['target']==target]
 assert len(actual)==20,(target,len(actual))
 for e in actual:
  atk=1155 if e['time']<5490 else 770
  assert abs(e['payload']['amount']-atk*(1-res/100))<1e-9,(target,e['time'],e['payload'])
ordinary=[e for e in rows('ability.started') if e['payload']['source']==boss and any('/'+s+'/' in e['payload']['ability'] for s in ('normal','ignite','explode'))]
assert not any(207<=e['time']<1047 or 4650<=e['time']<5490 for e in ordinary)
summons=[e for e in rows('ability.started') if e['payload']['source']==boss and e['payload']['ability']==summon]
assert summons and all(e['time']>=1047+2250 for e in summons)
branches=[e for e in rows('branch.phase_started') if e['payload']['branch']=='bsnake_flame']
assert branches and branches[0]['payload']['phase_index']==0 and branches[0]['payload']['actions']==5
devicecasts=[e for e in rows('ability.started') if e['payload']['ability']=='ability/ch8/flame/explode']
assert len(devicecasts)>=5
transfers=rows('timeline.source_transferred')
assert [(e['time'],e['payload']['source'],e['payload']['from_wave'],e['payload']['to_wave']) for e in transfers]==[(117,20,0,1)]
requests=rows('timeline.finish_requested')
assert [(e['time'],e['payload']['parameters']['track_source_at_next_wave']) for e in requests]==[(57,True),(4500,False)]
assert len(rows('command.accepted'))==2
report={'passed':True,'scope':'Controlled source two public defeats, first full75000 restoration, native screen7x10 twice, real Summon+Flame. Not44-birth whole/client; raw recharge mapping and ray/capture/coroutine reference policies explicit.','capture_sha':hashlib.sha256(raw).hexdigest(),'rays':len(rays),'screen_hits':len(hits),'volley_times':[e['time'] for e in volleys],'summon_times':[e['time'] for e in summons],'branch_times':[e['time'] for e in branches],'device_casts':devicecasts,'source_requests':requests,'source_transfers':transfers,'ordinary_casts':ordinary}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(hashlib.sha256((OUT/'verification.json').read_bytes()).hexdigest())
