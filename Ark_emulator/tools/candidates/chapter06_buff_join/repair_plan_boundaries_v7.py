"""Keep zero lifetime inert; reject malformed handles before keyed lookup."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PARENT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v6_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v7_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(path,before,after):
    text=path.read_text(encoding='utf8');assert text.count(before)==1
    path.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(PARENT)=='01f88963d0720245edfdbb7c3ca19dce2c307202795bba74ceb933f028d08a15' and not OUT.exists()
    shutil.copytree(PARENT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    replace(OUT/'ark_sim/domains/buffs.py',
        'if interval_units == 0 and current is not None and self.applicability.active(current):',
        'if interval_units == 0 and current is not None and self.applicability.active(current) and (current["expires_at"] is None or self.ctx.session.time < current["expires_at"]):')
    file=OUT/'ark_sim/domains/buff_application.py'
    replace(file,'len(set(allowed)) != len(allowed) or not all(isinstance(s, str) and s for s in allowed)',
                 'not all(isinstance(s, str) and s for s in allowed) or len(set(allowed)) != len(allowed)')
    replace(file,"uid, generation = op.get('instance'), op.get('generation')\n            old = owned.get(uid)",
                 "uid, generation = op.get('instance'), op.get('generation')\n            if not isinstance(uid, str) or not uid: raise ValueError('Remove handle requires a nonempty instance ID')\n            old = owned.get(uid)")
    changed={str(p.relative_to(OUT)): {'old_sha':sha(PARENT/p.relative_to(OUT)),'new_sha':sha(p)}
        for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and sha(p)!=sha(PARENT/p.relative_to(OUT))}
    assert set(changed)=={str(Path('ark_sim/domains/buffs.py')),str(Path('ark_sim/domains/buff_application.py'))}
    report={'parent_core':core(PARENT),'core':core(OUT),'changes':changed,'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
            'scope':'New source-preserving candidate; old failures retained; original independent boundary cases must be rerun'}
    target=ROOT/'validation/campaign/chapter06_buff_join_v7/repair.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
