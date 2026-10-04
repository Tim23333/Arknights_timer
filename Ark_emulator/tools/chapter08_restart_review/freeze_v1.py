import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'validation/campaign/chapter08_restart_independent_v6'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((OUT/'verification.json').read_bytes())
assert r['guards_equal'] and len(r['cases'])==17 and all(c['outcome']=='passed' for c in r['cases'])
files=list(OUT.rglob('*'))+[Path(__file__)]+list((ROOT/'tools/chapter08_restart_review').glob('*.py'))
old=[ROOT/f'validation/campaign/chapter08_restart_independent_v{i}/verification.json' for i in range(1,6)]
document={'passed':True,'core':r['core'],'cases':17,'unique_cases':17,'verification_sha':sha(OUT/'verification.json'),'scope':'Independent generic restart and clock checks on exact joint9ad: publiccast cancellation, finite unlistedcast preservation, strict invalid state/ability/clock/generation rejection, exit/enter retire short-circuit, recursive and latefault atomic rollback, real ownedBuff removal callback retire/fault and external Buff on different target preserved, self-enclosing dependency closure, clock expiry/pure nested evaluation/mutation/throw/noopt. Public ordered diskCP2 and clockCP3 SHAreload, full checkpoints+journals+public replay equality. No Talula source/fullstage/nativebody approval.','prior_fixture_failures':{str(p):sha(p) for p in old},'guards_start':r['guards_start'],'guards_end':r['guards_end'],'guards_equal':True,'artifact_pins':{str(p):sha(p) for p in sorted(set(files)) if p.is_file()},'fixture_corrections':'Old v1 floating at required at_seconds. v2 retire reason required parameters. v3 reason required event-safe text. v5 Buff.stacking required object. All old failed reports and input/captures retained unchanged; no candidate changed and assertions unchanged.'}
(OUT/'freeze.json').write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf8')
print(sha(OUT/'freeze.json'))
