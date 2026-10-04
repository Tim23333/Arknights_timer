"""Combine qualified area and selected-route obstacle without dropping gates."""
from pathlib import Path
import json,hashlib,shutil,sys
ROOT=Path(__file__).resolve().parents[3]
COMMON=ROOT.parent/'unpack_work/campaign_m52_visibility_stock_integrated_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m54_qualified_visibility_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m55_route_obstacle_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m56_chapter03_integrated_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate exists')
    for root,pin in [(COMMON,'bfbd9613dc36f2ac39c91381f57e8e4f7d306386514843d8b83ea020e45580fe'),(BASE,'e6e0142c9ef9aa2cdcf35188aba0865efba370346eecf1c50750a45f56974b75'),(INCOMING,'5c33c17ec6c7d7d1a1677e0df88176e594237e9d6485262e430c94dba86912ea')]:
        if core(root)!=pin:raise ValueError('Frozen branch core drift')
    evidence=ROOT/'validation/campaign/m55_obstacle/candidate_final.json'
    if sha(evidence)!='cc1fae9ea74479ad95ecf1c179327fe508fe04f12029a8af985aec7def10fd90':raise ValueError('Obstacle final report changed')
    sys.path.insert(0,str(ROOT/'tools/candidates/m54_integration'));from prepare import merge_text
    edits={};changed={}
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for p in sorted((INCOMING/'ark_sim').rglob('*')):
        if not p.is_file() or p.suffix not in ('.py','.json'):continue
        rel=p.relative_to(INCOMING/'ark_sim');old=COMMON/'ark_sim'/rel;current=BASE/'ark_sim'/rel;dest=OUT/'ark_sim'/rel
        if old.exists() and old.read_bytes()==p.read_bytes():continue
        if old.exists() and current.exists() and old.read_bytes()!=current.read_bytes():
            if rel.as_posix()!='content/capabilities.py':raise ValueError('Unexpected overlap '+str(rel))
            text,hunks=merge_text(old.read_text(),p.read_text(),current.read_text());dest.write_text(text,encoding='utf8',newline='');edits[rel.as_posix()]=hunks
        else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        changed[rel.as_posix()]=sha(dest)
    if set(edits)!={'content/capabilities.py'}:raise ValueError('Obstacle branch overlap changed')
    report={'schema':'ark-sim/chapter03-qualified-obstacle-integration/v1','core':core(OUT),'base_core':core(BASE),'incoming_core':core(INCOMING),
        'merged_hunks':edits,'changed_files':changed,'tested':False,'client_verified':False}
    out=ROOT/'validation/campaign/m56_integration/composition.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({'core':report['core'],'changes':list(changed)}))


if __name__=='__main__':main()
