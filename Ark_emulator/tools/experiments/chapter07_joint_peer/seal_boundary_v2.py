import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'validation/campaign/chapter07_boundary_cache_v2_original9_independent'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((OUT/'verification.json').read_text(encoding='utf8'))
assert r['core']=='06d5ef3772bdc01a52e313dd9c6d971050a018e1548bea1a949623a160baa8e7'
assert len(r['cases'])==9 and r['exit']==0 and r['guards_equal'] is True and all(x['outcome']=='passed' for x in r['cases'])
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix=='.json']+[p for p in Path(__file__).parent.glob('*.py')]
proof={'passed':True,'core':r['core'],'cases':9,'verification_sha':sha(OUT/'verification.json'),'guards_equal':True,'scope':'Original eight assertions and source CP6->36 unchanged; ninth initial CP0->36 source/public replay unchanged. Seven synthetic cross-scope/tile/foreignparent/task/retirement/fault cases, two actualsource diskCP/head cases. Actual one Immo116.704 packet derived1600*(1+.2+.2)*.0521. Native body policy/full stage/whole not signed. Old7696 tracefailure and70f6 CP0 tracefailure preserved.','files':{str(p):sha(p) for p in files}}
with (OUT/'freeze.json').open('x',encoding='utf8') as f:json.dump(proof,f,ensure_ascii=False,indent=2)
print(json.dumps({'verification_sha':proof['verification_sha'],'freeze_sha':sha(OUT/'freeze.json'),'core':proof['core'],'passed':True,'cases':9}))
