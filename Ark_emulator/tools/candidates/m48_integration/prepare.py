"""Integrate reviewed M46 area patch on M47; all parent files are immutable."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m44_chapter02_integrated_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m47_chapter02_reentry_integrated_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m46_area_members_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def core(root):
    rows={str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))}
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--incoming-core',required=True);ap.add_argument('--report-sha256',required=True);args=ap.parse_args()
    if OUT.exists():raise ValueError('M48 exists; frozen candidate cannot be overwritten')
    for root,pin in [(COMMON,'81d12ea08787d4edeed139ab55dc73e424644a1b4b8f48360fb9b114b25203da'),
        (BASE,'c7060a32668265e661c5a2e75f9361a693dca669239e6f883deac5b80fdae25b'),(INCOMING,args.incoming_core)]:
        if core(root)!=pin:raise ValueError('Frozen branch core drift')
    report=ROOT/'validation/campaign/m46_area/final.json'
    if sha(report)!=args.report_sha256:raise ValueError('Frozen M46 evidence drift')
    record=json.loads(report.read_bytes())
    if not record['passed'] or record['core_start']!=args.incoming_core or record['core_end']!=args.incoming_core or record['source_start']!=record['source_end']:
        raise ValueError('Incoming area report is not a stable successful run')
    changes={}
    for path in sorted((INCOMING/'ark_sim').rglob('*')):
        if not path.is_file() or path.suffix not in ('.py','.json'):continue
        relative=path.relative_to(INCOMING/'ark_sim');ancestor=COMMON/'ark_sim'/relative;current=BASE/'ark_sim'/relative
        if ancestor.exists() and path.read_bytes()==ancestor.read_bytes():continue
        if current.exists() and ancestor.exists() and current.read_bytes()!=ancestor.read_bytes() and current.read_bytes()!=path.read_bytes():
            raise ValueError('Explicit three-way merge required: '+str(relative))
        changes[str(relative)]=path
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,path in changes.items():
        destination=OUT/'ark_sim'/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    result={'schema':'ark-sim/frozen-area-integration/v1','common_core':core(COMMON),'base_core':core(BASE),
        'incoming_core':args.incoming_core,'integrated_core':core(OUT),'report_sha256':sha(report),
        'changed_files':{name:sha(path) for name,path in changes.items()},'tested':False,'client_verified':False}
    out=ROOT/'validation/campaign/m48_integration/composition.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'core':result['integrated_core'],'changed_files':len(changes)}))


if __name__=='__main__':main()
