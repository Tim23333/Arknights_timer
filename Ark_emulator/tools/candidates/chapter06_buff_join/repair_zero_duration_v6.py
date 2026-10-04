"""Preserve explicit zero-duration plans instead of treating them as permanent."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
PARENT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v5_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v6_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert core(PARENT)=='0fe88573f05b279aa3873ce5c2babaecce5e208cec8b1c7172052c3d1780b163'
    assert not OUT.exists()
    shutil.copytree(PARENT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    file=OUT/'ark_sim/domains/buffs.py';text=file.read_text(encoding='utf8')
    before='permanent = duration_units == 0 and "duration_seconds" not in definition and not definition.get("duration_rule")'
    after='permanent = duration_override is None and duration_units == 0 and "duration_seconds" not in definition and not definition.get("duration_rule")'
    assert text.count(before)==1
    file.write_text(text.replace(before,after),encoding='utf8',newline='')
    changes=[str(p.relative_to(OUT)) for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and sha(p)!=sha(PARENT/p.relative_to(OUT))]
    assert changes==[str(Path('ark_sim/domains/buffs.py'))]
    report={'parent_core':core(PARENT),'core':core(OUT),'changed_files':changes,'old_sha':sha(PARENT/'ark_sim/domains/buffs.py'),
            'new_sha':sha(file),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
            'scope':'Exact explicit-zero duration fix; no proof migration/primary/whole-stage approval'}
    target=ROOT/'validation/campaign/chapter06_buff_join_v6/repair.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
