import hashlib,json,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_frost_complete_v1_candidate'
OUT=ROOT.parent/'unpack_work/campaign_frost_complete_v2_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='99934175a5e70b976c9718e8244d20c2a3dad4e94388f10b08d2ac2fe0f5eda4'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    pattern=re.compile(r'(?m)^<<<<<<< .*?\n(.*?)^=======\n(.*?)^>>>>>>> .*?\n',re.S)
    def schema(match):
        left,right=match.group(1),match.group(2)
        if left.startswith('FIELDS = '):
            return left.replace("'ability': {'initial_cooldown_seconds',", "'ability': {'tile_selector','initial_cooldown_seconds',").replace(
                'COMPONENT_FIELDS = {','COMPONENT_FIELDS = {"tile_occupancy": {"blocks_deployment", "exclusive", "targetable", "withdrawable"},')
        return left+right
    p=OUT/'ark_sim/content/schemas.py';s=p.read_text(encoding='utf8');s,count=pattern.subn(schema,s);assert count==2
    p.write_text(s,encoding='utf8',newline='')
    p=OUT/'ark_sim/domains/lifecycle.py';s=p.read_text(encoding='utf8')
    def lifecycle(match):
        left=match.group(1)
        return left.replace('        if not has_initial_clocks and not has_connectivity',
            '        if not has_initial_clocks and "tile_occupancy" not in definition.get("components",{}) and "tile_occupancy" not in (kwargs.get("component_overrides") or {}) and not has_connectivity')
    s,count=pattern.subn(lifecycle,s);assert count==1;p.write_text(s,encoding='utf8',newline='')
    for p in (OUT/'ark_sim').rglob('*.py'):
        s=p.read_text(encoding='utf8');assert '<<<<<<<' not in s and '>>>>>>>' not in s
        compile(s,str(p),'exec')
    report={'parent_composition_core':core(BASE),'core':core(OUT),'candidate':str(OUT),
        'resolutions':['ability fields union','component fields union','both strict initial/tile validation',
            'lifecycle atomic fast-path gate union'], 'full_stage_executed':False}
    target=ROOT/'validation/campaign/frost_complete_v1/composition_resolved.json'
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
