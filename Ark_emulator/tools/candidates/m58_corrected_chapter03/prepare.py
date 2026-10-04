"""Combine frozen obstacle callback revision with qualified-primary revision."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m56_chapter03_integrated_candidate'
OBSTACLE=ROOT.parent/'unpack_work/campaign_m57_obstacle_reentry_candidate'
PRIMARY=ROOT.parent/'unpack_work/campaign_m59_area_primary_candidate'
OBSTACLE_PARENT=ROOT.parent/'unpack_work/campaign_m55_route_obstacle_candidate'
PRIMARY_PARENT=ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m58_corrected_chapter03_candidate'
PINS={BASE:'9fd0e2e11e19ad3573b9f85b49cff52ae6503cc031e44124d452c5972294f011',
      OBSTACLE:'9e4d255d153950ce6d74ae24b27885a6247dd4872c91e9e7ff181d6e5a99bf70',
      PRIMARY:'84b4146bd574dda5dfd833314bee46c4370e583bcc8ef900075911fdafadbd9a',
      OBSTACLE_PARENT:'5c33c17ec6c7d7d1a1677e0df88176e594237e9d6485262e430c94dba86912ea',
      PRIMARY_PARENT:'e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'}


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate already exists; no overwrite')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen source core changed:'+str(root))
    reports={ROOT/'validation/campaign/m57_obstacle_reentry/final.json':'b68fb5fb7e2de568295808388aba9d45484bc61782d0ab44e277fe860c7452e1',
             ROOT/'validation/campaign/m59_area_primary/candidate_final.json':'09f9d50a164bc0eadf640c42167ebd492a9d215550f102af3d57c0ee361db5f8'}
    for p,pin in reports.items():
        if sha(p)!=pin:raise ValueError('Frozen review report changed')
    changes={}
    for incoming,parent,expected in [(OBSTACLE,OBSTACLE_PARENT,{'domains/movement.py'}),(PRIMARY,PRIMARY_PARENT,{'domains/qualified_areas.py'})]:
        diff={p.relative_to(incoming/'ark_sim').as_posix() for p in (incoming/'ark_sim').rglob('*.py') if p.read_bytes()!=(parent/'ark_sim'/p.relative_to(incoming/'ark_sim')).read_bytes()}
        if diff!=expected:raise ValueError('Unexpected branch changes:'+str(diff))
        for rel in diff:
            if (BASE/'ark_sim'/rel).read_bytes()!=(parent/'ark_sim'/rel).read_bytes():raise ValueError('Overlapping unreviewed branch:'+rel)
            changes[rel]=sha(incoming/'ark_sim'/rel)
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for incoming,rel in [(OBSTACLE,'domains/movement.py'),(PRIMARY,'domains/qualified_areas.py')]:
        shutil.copyfile(incoming/'ark_sim'/rel,OUT/'ark_sim'/rel)
    # Pure offline JSON only for source-import tests, never V1 implementation.
    offline=ROOT/'ark_emulator/levels/packs/level_main_00-01.json'
    dest=OUT/'ark_emulator/levels/packs/level_main_00-01.json';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(offline,dest)
    report={'schema':'ark-sim/corrected-chapter03-integration/v1','core':core(OUT),'source_cores':{str(p):pin for p,pin in PINS.items()},
        'changed_files':changes,'reports':{str(p):pin for p,pin in reports.items()},'offline_data_sha256':sha(dest),'tested':False,'actual_client_verified':False}
    output=ROOT/'validation/campaign/m58_integration/composition.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'core':report['core'],'changes':list(changes)}))


if __name__=='__main__':main()
