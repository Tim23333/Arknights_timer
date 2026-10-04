"""Three-way source composition; explicit conflicts remain reviewable."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'
LEFT=ROOT.parent/'unpack_work/campaign_ability_arbitration_v3_candidate'
RIGHT=ROOT.parent/'unpack_work/campaign_tile_targets_v8_candidate'
OUT=ROOT.parent/'unpack_work/campaign_frost_complete_v1_candidate'
PINS={BASE:'cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7',
      LEFT:'455de2ea24f042c445483b9c05df6c1e95421db496be385e034f99ec3f20f1ae',
      RIGHT:'99a7aeff1cfe91806b1c0cf283e138fce75a5150d821535976072e4dd3080074'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert all(core(p)==pin for p,pin in PINS.items())
    if OUT.exists():raise FileExistsError('Preserve composition candidate')
    shutil.copytree(LEFT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    conflicts=[];changed=[]
    for p in sorted((RIGHT/'ark_sim').rglob('*')):
        if not p.is_file() or p.suffix not in {'.py','.json'}:continue
        rel=p.relative_to(RIGHT);base=BASE/rel;left=LEFT/rel;target=OUT/rel
        if base.exists() and sha(base)==sha(p):continue
        changed.append(str(rel))
        if not left.exists() or base.exists() and sha(left)==sha(base):
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        elif sha(left)!=sha(p):
            assert base.exists(),str(rel)
            result=subprocess.run(['git','merge-file','-p',str(left),str(base),str(p)],capture_output=True)
            assert result.returncode in (0,1,2,3),result.stderr
            target.write_bytes(result.stdout)
            if result.returncode:conflicts.append(str(rel))
    report={'source_cores':{str(p):pin for p,pin in PINS.items()},'right_changed_files':changed,
        'conflicts':conflicts,'core_with_conflicts':core(OUT),'not_accepted':True}
    dest=ROOT/'validation/campaign/frost_complete_v1/composition_initial.json';dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
