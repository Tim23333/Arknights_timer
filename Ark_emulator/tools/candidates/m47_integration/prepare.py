"""Integrate M45's frozen Buff-only change with frozen M44 terrain/requests."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m44_chapter02_integrated_candidate'
PARENT=ROOT.parent/'unpack_work/campaign_m42_aura_remove_candidate'
PATCH=ROOT.parent/'unpack_work/campaign_m45_aura_reentry_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m47_chapter02_reentry_integrated_candidate'
PINS={BASE:'81d12ea08787d4edeed139ab55dc73e424644a1b4b8f48360fb9b114b25203da',
      PARENT:'2746020dd269241d8802551ea63cb28243755ff0105a19bb09033c448f497420',
      PATCH:'181eb512eaa01234775ab6ebfdb7ada7f98cb6eea998093bc31a3cb412c39670'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def core(root):
    rows={str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))}
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('New integrated candidate already exists')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen candidate drift: '+str(root))
    report_path=ROOT/'validation/campaign/m45_aura_reentry/candidate_final.json'
    if sha(report_path)!='561e8288721ac88bd3b25565ad538e7097f9f4e9185322b39f88d5857826640e':raise ValueError('Frozen M45 report drift')
    report=json.loads(report_path.read_bytes())
    if not report['source_unchanged'] or any(case['outcome']!='passed' for case in report['cases']):raise ValueError('M45 new cases have not passed')
    changed=[]
    for file in sorted((PATCH/'ark_sim').rglob('*.py')):
        rel=file.relative_to(PATCH/'ark_sim');old=PARENT/'ark_sim'/rel
        if old.read_bytes()!=file.read_bytes():changed.append(str(rel))
    if changed!=[str(Path('domains/buffs.py'))]:raise ValueError('M45 unexpectedly changed other files')
    if (BASE/'ark_sim/domains/buffs.py').read_bytes()!=(PARENT/'ark_sim/domains/buffs.py').read_bytes():raise ValueError('Buff branch requires explicit three-way merge')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(PATCH/'ark_sim/domains/buffs.py',OUT/'ark_sim/domains/buffs.py')
    result={'schema':'ark-sim/frozen-buff-branch-integration/v1','integrated_core':core(OUT),'source_cores':{str(k):v for k,v in PINS.items()},
        'm45_report_sha256':sha(report_path),'changed_file':'domains/buffs.py','changed_file_sha256':sha(OUT/'ark_sim/domains/buffs.py'),
        'source_merging_conflicts':False,'tested':False,'actual_client_verified':False}
    out=ROOT/'validation/campaign/m47_integration/composition.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'core':result['integrated_core'],'candidate':str(OUT)}))


if __name__=='__main__':main()
