"""Keep zero lifetime inert; reject malformed handles before keyed lookup."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PARENT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v8_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(path,before,after):
    text=path.read_text(encoding='utf8');assert text.count(before)==1
    path.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(PARENT)=='13c8f6f856ea622d35604cc88cd4122b0dc6e5f985be4eedfba46699d2b8c42b' and not OUT.exists()
    shutil.copytree(PARENT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    replace(OUT/'ark_sim/domains/buffs.py',
        '        for instance in instances:\n            if not self.applicability.active(instance):continue',
        '        for instance in instances:\n            if instance.get("expires_at") is not None and self.ctx.session.time >= instance["expires_at"]: continue\n            if not self.applicability.active(instance):continue')
    changed={str(p.relative_to(OUT)): {'old_sha':sha(PARENT/p.relative_to(OUT)),'new_sha':sha(p)}
        for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and sha(p)!=sha(PARENT/p.relative_to(OUT))}
    assert set(changed)=={str(Path('ark_sim/domains/buffs.py'))}
    report={'parent_core':core(PARENT),'core':core(OUT),'changes':changed,'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
            'scope':'New source-preserving candidate; old failures retained; original independent boundary cases must be rerun'}
    target=ROOT/'validation/campaign/chapter06_buff_join_v9/repair.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
