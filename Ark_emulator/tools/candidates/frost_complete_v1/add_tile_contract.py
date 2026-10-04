import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v3_candidate'
OUT=ROOT.parent/'unpack_work/campaign_frost_complete_v4_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='ddd1707b6faba798fac9de0a0b5a92ffb9a49067ade89850f2b2d396d3c46749'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/rules/contracts.json';data=json.loads(p.read_bytes())
    contract=next(c for c in data['contracts'] if c['id']=='behavior.decision')
    assert not any(row['name']=='tile_candidates' for row in contract['inputs'])
    contract['inputs'].append({'name':'tile_candidates','type':'record','required':False})
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    p=OUT/'ark_sim/domains/behavior_decision.py';s=p.read_text(encoding='utf8')
    p.write_text(s.replace('"""Opt-in strict behavior decisions from declared profiles and pure facts."""',
        '"""Opt-in behavior decisions, including optional pure declared tile candidates."""'),encoding='utf8',newline='')
    target=ROOT/'validation/campaign/frost_complete_v1/tile_contract_composition.json'
    report={'parent_core':core(BASE),'core':core(OUT),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'contract_addition':'behavior.decision optional record tile_candidates','full_stage_executed':False}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
