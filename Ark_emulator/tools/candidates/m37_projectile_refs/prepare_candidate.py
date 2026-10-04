"""New frozen-parent branch: canonicalize target before quota reservations."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m30_projectile_quota_candidate';OUT=ROOT.parent/'unpack_work/campaign_m37_projectile_refs_candidate'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='517290e56f59bdf5f57862dbadb8929b37cf6fbe0468116dcb39669df6357b51'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
p=OUT/'ark_sim/domains/projectiles.py';old=b"  target=x['trace_target'] if target is None else target\r\n";raw=p.read_bytes()
if old not in raw:old=old.replace(b'\r\n',b'\n')
new=old+b"  target=self.ctx.session.world.resolve(target)"+(b'\r\n' if old.endswith(b'\r\n') else b'\n')
if new not in raw:assert raw.count(old)==1;raw=raw.replace(old,new);p.write_bytes(raw)
changed=[x.relative_to(OUT/'ark_sim').as_posix() for x in sorted((OUT/'ark_sim').rglob('*.py')) if sha(x)!=sha(BASE/'ark_sim'/x.relative_to(OUT/'ark_sim'))];assert changed==['domains/projectiles.py']
print(json.dumps({'core':core(OUT),'candidate':str(OUT),'changed':changed}))
