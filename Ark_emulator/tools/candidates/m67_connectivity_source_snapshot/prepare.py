"""Fix peer's genuine source snapshot variable shadowing in a new revision."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m66_connectivity_activation_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m67_connectivity_snapshot_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    if core(BASE)!='5426771f40d61d02846d480a41bde904869b10d37b3e94e8fce8c4e64b009dd9':raise ValueError('Frozen activation parent changed')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/deploy_connectivity.py';s=p.read_text(encoding='utf8')
    old="""    for entity in context.session.world.entities():
        if not context.active(entity['id']) or context.route_hidden(entity['id']):continue
        if not entity['components'].get('route_obstacle'):continue
        other=entity['components'].get('spatial',{}).get('position')"""
    new="""    for candidate in context.session.world.entities():
        if not context.active(candidate['id']) or context.route_hidden(candidate['id']):continue
        if not candidate['components'].get('route_obstacle'):continue
        other=candidate['components'].get('spatial',{}).get('position')"""
    if s.count(old)!=1:raise ValueError('Shadowing source anchor changed')
    p.write_text(s.replace(old,new,1),encoding='utf8',newline='')
    report={'core':core(OUT),'parent':core(BASE),'changed_file':'domains/deploy_connectivity.py','source_sha256':sha(p),'tested':False,
        'scope':'Keep the explicit entity argument; scanning obstacles must not replace proposed/current actor snapshot'}
    f=ROOT/'validation/campaign/m67_connectivity/composition.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
