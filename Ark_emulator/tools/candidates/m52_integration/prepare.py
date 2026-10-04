"""Explicit stock/payment + visibility integration, frozen parent validation."""
import argparse,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m51_deploy_payment_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m49_visibility_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m52_visibility_stock_integrated_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--incoming-core',required=True);ap.add_argument('--report-sha256',required=True);args=ap.parse_args()
    if OUT.exists():raise ValueError('Candidate exists; do not overwrite')
    for path,pin in [(COMMON,'a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9'),(BASE,'50902adad7bd99b27b4c3c2efd2d40e97458bb181d203f5b434fcd0eaa782c1f'),(INCOMING,args.incoming_core)]:
        if core(path)!=pin:raise ValueError('Frozen branch drift')
    report=ROOT/'validation/campaign/m49_visibility/final.json'
    if sha(report)!=args.report_sha256:raise ValueError('M49 report drift')
    evidence=json.loads(report.read_bytes())
    if not evidence['passed'] or evidence['source_start']!=evidence['source_end'] or evidence['core_start']!=args.incoming_core or evidence['core_end']!=args.incoming_core:raise ValueError('M49 source cases have not passed stably')
    changed={};overlaps=[]
    for path in sorted((INCOMING/'ark_sim').rglob('*')):
        if not path.is_file() or path.suffix not in ('.py','.json'):continue
        rel=path.relative_to(INCOMING/'ark_sim');old=COMMON/'ark_sim'/rel;current=BASE/'ark_sim'/rel
        if old.exists() and old.read_bytes()==path.read_bytes():continue
        if old.exists() and current.exists() and current.read_bytes()!=old.read_bytes():overlaps.append(rel.as_posix())
        changed[rel.as_posix()]=path
    if overlaps!=['content/schemas.py']:raise ValueError('Unreviewed overlapping branches: '+str(overlaps))
    original=(COMMON/'ark_sim/content/schemas.py').read_text(encoding='utf8');incoming=(INCOMING/'ark_sim/content/schemas.py').read_text(encoding='utf8');merged=(BASE/'ark_sim/content/schemas.py').read_text(encoding='utf8')
    replacements=[('"buff": {"contact_flags",','"buff": {"toggle", "contact_flags",'),
        ('    elif kind == "buff":\n','    elif kind == "buff":\n        if "toggle" in definition:\n            from ..domains.toggles import validate\n            validate(definition["toggle"],identifier+".toggle")\n')]
    expected=original
    for old,new in replacements:
        if expected.count(old)!=1 or merged.count(old)!=1:raise ValueError('Schema merge context drift')
        expected=expected.replace(old,new,1);merged=merged.replace(old,new,1)
    if expected!=incoming:raise ValueError('Incoming schema has changes beyond reviewed toggle hunks')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,path in changed.items():
        if name=='content/schemas.py':continue
        dest=OUT/'ark_sim'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    (OUT/'ark_sim/content/schemas.py').write_text(merged,encoding='utf8',newline='')
    result={'schema':'ark-sim/explicit-visibility-stock-integration/v1','integrated_core':core(OUT),'common_core':core(COMMON),'stock_payment_core':core(BASE),'visibility_core':args.incoming_core,
        'incoming_report_sha256':sha(report),'overlapping_file':'content/schemas.py','merge':'Only two verified incoming toggle hunks applied to stock schema; all other branch differences byte copied',
        'incoming_files':{n:sha(p) for n,p in changed.items()},'tested':False,'client_verified':False}
    out=ROOT/'validation/campaign/m52_integration/composition.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({'core':result['integrated_core'],'incoming_files':len(changed)}))


if __name__=='__main__':main()
