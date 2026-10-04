"""New revision for never-activated source isolation; preserve db6134 evidence."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent/'unpack_work/campaign_m20_dormant_candidate'
OUT = ROOT.parent/'unpack_work/campaign_m20_dormant_source_candidate'
PIN = 'db6134da42647f1691f8b6fb5318fa8bbbcc455b26b1dc59841d6c1eba95bdcc'


def main():
    code = 'import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    if subprocess.check_output([sys.executable, '-c', code, str(BASE)], cwd=BASE, text=True).strip() != PIN:
        raise ValueError('frozen parent dormant core drift')
    if OUT.exists() or OUT.parent.resolve() != (ROOT.parent/'unpack_work').resolve():
        raise ValueError('new named candidate required; never overwrite old evidence')
    shutil.copytree(BASE/'ark_sim', OUT/'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    def patch(relative, old, new):
        p = OUT/relative; s = p.read_text(encoding='utf8')
        if s.count(old) != 1: raise ValueError('unexpected source shape: '+relative)
        p.write_text(s.replace(old, new), encoding='utf8', newline='\n')
    patch('ark_sim/domains/effects.py', '        ability, cast = ability or {}, cast or {}', '''        ability, cast = ability or {}, cast or {}
        if (not self.ctx.get(source, ('runtime', 'active'), True) and self.ctx.get(source, ('runtime', 'state')) == 'dormant'
                and effect['op'] not in {'activate_predefined', 'retire', 'emit', 'remove_buff', 'remove_terrain_overlay'}):
            self.ctx.emit('effect.source_inactive_rejected', {'source': source, 'targets': list(targets), 'operation': effect['op']}, cause)
            return''')
    # A registered actor that later revives must resume participation. Dormant
    # templates do not run a death/revival rule before their activation boundary.
    patch('ark_sim/domains/lifecycle.py', '    def check(self, ref, event):\n        lifecycle', "    def check(self, ref, event):\n        if not self.ctx.get(ref, ('runtime', 'active'), True) and self.ctx.get(ref, ('runtime', 'state')) == 'dormant':\n            return\n        lifecycle")
    patch('ark_sim/domains/lifecycle.py', '        elif plan["action"] == "revive":\n            self.ctx.set(ref, ("runtime", "alive"), True)', '''        elif plan["action"] == "revive":
            if 'active' in self.ctx.get(ref, ('runtime',)):
                self.ctx.set(ref, ('runtime', 'active'), True)
            self.ctx.set(ref, ("runtime", "alive"), True)''')
    print(subprocess.check_output([sys.executable, '-c', code, str(OUT)], cwd=OUT, text=True).strip())


if __name__ == '__main__': main()
