"""Expose declared tile ability candidates to pure behavior decision rules."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v2_candidate'
OUT=ROOT.parent/'unpack_work/campaign_frost_complete_v3_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='a115e421da1a551bf76aa1a7cfa013f2efd51a60b8c1685e8353675327acd95c'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/behavior_decision.py';s=p.read_text(encoding='utf8')
    old=" return {'source':ctx.entity(ref),'state':state,'mode':mode,'casts':casts,'cast_groups':groups,"
    new=" tile_candidates={}\n for aid in ctx.get(ref,('abilities',),[]):\n  ability=ctx.program.definitions[aid]\n  if ability.get('tile_selector'):\n   from .tile_targets import query\n   tile_candidates[aid]=query(ctx,ref,ability['tile_selector'])[:ability['tile_selector']['limit']]\n return {'tile_candidates':tile_candidates,'source':ctx.entity(ref),'state':state,'mode':mode,'casts':casts,'cast_groups':groups,"
    assert s.count(old)==1;p.write_text(s.replace(old,new),encoding='utf8',newline='')
    report={'parent_core':core(BASE),'core':core(OUT),'changed':['domains/behavior_decision.py'],'full_stage_executed':False}
    target=ROOT/'validation/campaign/frost_complete_v1/tile_facts_composition.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
