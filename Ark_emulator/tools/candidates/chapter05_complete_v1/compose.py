"""Source composition draft; independent constituent verification remains required."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v5_candidate'
LEFT=ROOT.parent/'unpack_work/campaign_selection_settle_v3_candidate';RIGHT=ROOT.parent/'unpack_work/campaign_ballista_directional_v1_candidate'
OUT=ROOT.parent/'unpack_work/campaign_chapter05_complete_v1_candidate'
PINS={BASE:'7a04c12a1a4224eecbd25b495d84c27da0096ceef7d01f50f1a1c8c9b8da7d90',
      LEFT:'30e4cdfadc5a98eb59da20d89591f5f5d3d6acc8f2d9a997df5e761d759fb49d',
      RIGHT:'49af646affbd800b2d65a25634700deb1444fcbc3e0d886516ad9509edab217b'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert all(core(p)==pin for p,pin in PINS.items())
    if OUT.exists():raise FileExistsError('Preserve composition')
    shutil.copytree(LEFT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    conflicts=[];changes=[]
    for p in sorted((RIGHT/'ark_sim').rglob('*')):
        if not p.is_file() or p.suffix not in {'.py','.json'}:continue
        rel=p.relative_to(RIGHT);base=BASE/rel;left=LEFT/rel;target=OUT/rel
        if base.exists() and sha(p)==sha(base):continue
        changes.append(str(rel))
        if not left.exists() or base.exists() and sha(left)==sha(base):target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        elif sha(left)!=sha(p):
            assert base.exists();r=subprocess.run(['git','merge-file','-p',str(left),str(base),str(p)],capture_output=True)
            assert r.returncode in (0,1,2,3);target.write_bytes(r.stdout)
            if r.returncode:conflicts.append(str(rel))
    assert all(core(p)==pin for p,pin in PINS.items())
    report={'source_cores':{str(p):pin for p,pin in PINS.items()},'core':core(OUT),'changes':changes,'conflicts':conflicts,
        'status':'Draft; author Ballista final/independent verification, combined checks, full stage all pending'}
    out=ROOT/'validation/campaign/chapter05_complete_v1/composition.json';out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
