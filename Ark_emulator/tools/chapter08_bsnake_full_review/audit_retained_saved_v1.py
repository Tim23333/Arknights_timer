"""Verify actual captures preserved before the v1 report serializer failure."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'validation/campaign/chapter08_bsnake_retained_source_v1'
OUT=ROOT/'validation/campaign/chapter08_bsnake_retained_saved_audit_v1';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
captures=[json.loads((BASE/(name+'.json')).read_bytes()) for name in ('forward','restored','head')]
a,b,c=captures
assert a['checkpoint']==b['checkpoint']==c['checkpoint']
assert a['events']==b['events']==c['events']
hits=[e for e in a['events'] if e['type']=='damage.accepted' and e['payload']['ability']=='ability/ch8/bsnake/firecommon']
assert len(hits)==7
for ref,res in zip(range(13,20),[17,37,53,73,17,37,53]):
 found=[e for e in hits if e['payload']['target']==ref];assert len(found)==1
 assert found[0]['time']>268 and abs(found[0]['payload']['amount']-770*(1-res/100))<1e-9
report={'passed':True,'actual_core':'82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae','scope':'Actual independent saved public launch267/skipRebirthTrue defeat268/7 later770ATK hits and orderedCP/publichead equality. Original v1 execution reached all assertions and saved3 captures before report writer failed FrozenMapping JSON serialization. That exit1 is preserved; this separate read-only verifier does not relabel it exit0. Not140 full orwhole.','original_writer_failure':'TypeError Object of type FrozenMapping is not JSON serializable','capture_pins':{name:sha(BASE/(name+'.json')) for name in ('forward','restored','head')},'input_sha':sha(BASE/'input.json'),'commands_sha':sha(BASE/'commands.json'),'hits':hits}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(sha(OUT/'verification.json'))
