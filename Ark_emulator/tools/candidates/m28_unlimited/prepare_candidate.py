"""Copy frozen M26, minimally extend generic projectile total hit capacity."""
from pathlib import Path
import shutil,json,hashlib
ROOT=Path(__file__).resolve().parents[3];SOURCE=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate';TARGET=ROOT.parent/'unpack_work/campaign_m28_unlimited_projectile_candidate'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(SOURCE)=='7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe'
if not TARGET.exists():shutil.copytree(SOURCE,TARGET,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
def replace(relative,before,after):
 p=TARGET/'ark_sim'/relative;raw=p.read_bytes();old=before.encode();new=after.encode()
 if old in raw:assert raw.count(old)==1;raw=raw.replace(old,new);p.write_bytes(raw)
 else:assert new in raw,'unexpected candidate state: '+relative
replace('content/schemas.py','if type(definition.get("max_hits")) is not int or definition["max_hits"] < 0: raise ContentError(identifier+".max_hits: nonnegative integer required")','if "max_hits" not in definition or (definition["max_hits"] is not None and (type(definition["max_hits"]) is not int or definition["max_hits"] < 0)): raise ContentError(identifier+".max_hits: explicit nonnegative integer or null (unlimited) required")')
replace('domains/projectiles.py',"if x['hit_count']>=d['max_hits'] or (not d['can_hit_same_target'] and target in x['hit_targets']):return False","if (d['max_hits'] is not None and x['hit_count']>=d['max_hits']) or (not d['can_hit_same_target'] and target in x['hit_targets']):return False")
replace('domains/projectiles.py',"(d['stop_after_max'] and x['hit_count']>=d['max_hits'])","(d['stop_after_max'] and d['max_hits'] is not None and x['hit_count']>=d['max_hits'])")
replace('domains/projectiles.py',"   for hit in hits:self._hit(x,d,hit)","   for hit in hits:\n    if self._hit(x,d,hit) and d['stop_after_first']:break")
changed=[p.relative_to(TARGET/'ark_sim').as_posix() for p in sorted((TARGET/'ark_sim').rglob('*.py')) if sha(p)!=sha(SOURCE/'ark_sim'/p.relative_to(TARGET/'ark_sim'))]
assert changed==['content/schemas.py','domains/projectiles.py']
print(json.dumps({'candidate':str(TARGET),'parent':core(SOURCE),'core':core(TARGET),'changed':changed}))
