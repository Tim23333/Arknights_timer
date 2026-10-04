"""Compose strict disk journal with corrected environment/death V2 runtime."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.candidates.m79_rebirth_environment.prepare import core,merge
COMMON=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m88_corrected_death_environment_candidate'
INCOMING=ROOT.parent/'unpack_work/campaign_m81_strict_event_reference_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m82_disk_environment_candidate'
PINS={COMMON:'1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8',
      BASE:'3577e4cd2621218cbb819f3c4b21f32922f562c9176d26ab80681bc91f587af1',
      INCOMING:'9f0d15e6f84bcff2eb5f08f3a04f7753a5f3f952f904798f24808427e7f51b9e'}


def main():
    if OUT.exists():raise ValueError('Preserve existing candidate')
    for root,pin in PINS.items():
        if core(root)!=pin:raise ValueError('Frozen source changed')
    writes={};hunks={}
    for p in (INCOMING/'ark_sim').rglob('*.py'):
        rel=p.relative_to(INCOMING/'ark_sim');a=COMMON/'ark_sim'/rel;c=BASE/'ark_sim'/rel
        if a.exists() and a.read_bytes()==p.read_bytes():continue
        if not a.exists():writes[rel.as_posix()]=p.read_text(encoding='utf8');continue
        try:value,rows=merge(a.read_text(encoding='utf8'),p.read_text(encoding='utf8'),c.read_text(encoding='utf8'))
        except ValueError as error:raise ValueError(rel.as_posix()+': '+str(error)) from error
        writes[rel.as_posix()]=value;hunks[rel.as_posix()]=rows
    shutil.copytree(BASE,OUT,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name,value in writes.items():(OUT/'ark_sim'/name).write_text(value,encoding='utf8',newline='')
    report={'parent_pins':{str(k):v for k,v in PINS.items()},'core':core(OUT),'writes':sorted(writes),'hunks':hunks,
        'scope':'Constructed disk/env/death candidate; no source evidence inherited as acceptance, tests pending'}
    out=ROOT/'validation/campaign/m82_disk_environment';out.mkdir(parents=True,exist_ok=True);(out/'composition.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({'core':report['core'],'writes':report['writes']}))


if __name__=='__main__':main()
