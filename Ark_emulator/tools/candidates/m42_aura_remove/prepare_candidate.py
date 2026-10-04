"""New branch: outermost remove reconciles membership in the same transaction."""
from pathlib import Path
import shutil,hashlib,json
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate';OUT=ROOT.parent/'unpack_work/campaign_m42_aura_remove_candidate';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert core(BASE)=='2165e5e267fa62012867d7676e0ad68f53234217e0b62fec31ace3956f23fdd6'
if not OUT.exists():shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
p=OUT/'ark_sim/domains/buffs.py';raw=p.read_bytes()
def change(before,after):
 global raw
 old=before.encode();new=after.encode()
 if old not in raw and b'\r\n' not in raw:old=old.replace(b'\r\n',b'\n');new=new.replace(b'\r\n',b'\n')
 if old in raw:assert raw.count(old)==1;raw=raw.replace(old,new)
 else:assert new in raw
change('        self._reconciling = False\r\n        self.has_auras','        self._reconciling = False\r\n        self._removal_depth = 0\r\n        self.has_auras')
change('    def remove(self, target, buff_or_instance):\r\n        with self.ctx.session.atomic():', '    def remove(self, target, buff_or_instance):\r\n        with self.ctx.session.atomic():\r\n            self._removal_depth += 1\r\n            try:\r\n                removed = self._remove(target, buff_or_instance)\r\n            finally:\r\n                self._removal_depth -= 1\r\n            if removed and self._removal_depth == 0:\r\n                self.reconcile()\r\n            return removed\r\n\r\n    def _remove(self, target, buff_or_instance):\r\n        with self.ctx.session.atomic():')
change('        if not self.has_auras or self._reconciling:\r\n','        if not self.has_auras or self._reconciling or self._removal_depth:\r\n')
p.write_bytes(raw);changed=[x.relative_to(OUT/'ark_sim').as_posix() for x in sorted((OUT/'ark_sim').rglob('*.py')) if sha(x)!=sha(BASE/'ark_sim'/x.relative_to(OUT/'ark_sim'))];assert changed==['domains/buffs.py']
print(json.dumps({'candidate':str(OUT),'core':core(OUT),'changed':changed}))
