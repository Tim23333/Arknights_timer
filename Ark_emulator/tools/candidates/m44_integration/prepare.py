"""Integrate frozen M41 contact, M42 Buff removal and M43 request transforms."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m44_chapter02_integrated_candidate'
BRANCHES={
    'campaign_m41_hole_contact_candidate':'43cdc7a22226ed71c8743976254048e6d4fd2258fff6668f06eb2966e78fe9d3',
    'campaign_m42_aura_remove_candidate':'2746020dd269241d8802551ea63cb28243755ff0105a19bb09033c448f497420',
    'campaign_m43_request_transform_candidate':'f58f3594fe12dbf35f070effba48984871469f4799f19d7004b24c0ab5bd6c11'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def core(root):
    rows={str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))}
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()


def main():
    if OUT.exists():raise ValueError('Integrated candidate already exists; do not overwrite frozen identity')
    if core(BASE)!='2165e5e267fa62012867d7676e0ad68f53234217e0b62fec31ace3956f23fdd6':raise ValueError('Base identity drift')
    changes={};origins={}
    for name,pin in BRANCHES.items():
        branch=ROOT.parent/'unpack_work'/name
        if core(branch)!=pin:raise ValueError('Frozen branch drift: '+name)
        for path in sorted((branch/'ark_sim').rglob('*')):
            if not path.is_file() or path.suffix not in ('.py','.json'):continue
            relative=path.relative_to(branch/'ark_sim');old=BASE/'ark_sim'/relative
            if old.exists() and old.read_bytes()==path.read_bytes():continue
            if str(relative) in changes and changes[str(relative)].read_bytes()!=path.read_bytes():
                raise ValueError('Explicit merge required for overlapping file '+str(relative))
            changes[str(relative)]=path;origins.setdefault(str(relative),[]).append({'branch':name,'core':pin,'source_sha256':sha(path)})
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,path in changes.items():
        destination=OUT/'ark_sim'/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    report={'schema':'ark-sim/frozen-branch-integration/v1','base':core(BASE),'integrated_core':core(OUT),
        'candidate':str(OUT),'changed_files':origins,'tested':False,'actual_client_verified':False}
    out=ROOT/'validation/campaign/m44_integration/composition.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'core':report['integrated_core'],'changed_files':len(origins)}))


if __name__=='__main__':main()
