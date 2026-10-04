"""Authorize actual resolved area recipients within the retained packet lineage."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v15_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_area_payload_v16_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(p,before,after):
    text=p.read_text(encoding='utf8');assert text.count(before)==1,(str(p),before)
    p.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(BASE)=='b3d51a11e499b693e22cf7750555629423b009413ed2d84a6d3ffb3dccace2c6' and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    proj=OUT/'ark_sim/domains/projectiles.py'
    replace(proj,'import math','import math\nfrom contextlib import contextmanager')
    replace(proj,'  self._impact_payload_scopes=[]','  self._impact_payload_scopes=[]\n  self._area_payload_scopes=[]')
    replace(proj,' def retained_payload_allowed(self,source,target,cast):',
        ''' @contextmanager
 def payload_area(self,source,cast,members):
  # Only the area executor, after validating actual members, owns this scope.
  added=[]
  for scope in self._impact_payload_scopes:
   if source==scope['source'] and cast is scope['cast']:
    entry={'impact':scope,'members':{ref:self.payload_incarnation(ref) for ref in members}}
    self._area_payload_scopes.append(entry);added.append(entry)
  try:yield
  finally:
   for entry in reversed(added):
    assert self._area_payload_scopes[-1] is entry
    self._area_payload_scopes.pop()
 def retained_payload_allowed(self,source,target,cast):''')
    replace(proj,"   if scope['source']!=source or scope['target']!=target or cast is not scope['cast']:continue",
        "   if scope['source']!=source or cast is not scope['cast']:continue")
    replace(proj,"   if target not in self._inflight_hits.get(scope['projectile'],[]):continue",
        "   if scope['target'] not in self._inflight_hits.get(scope['projectile'],[]):continue")
    replace(proj,"   if self.payload_incarnation(source)!=scope['source_identity'] or self.payload_incarnation(target)!=scope['target_identity']:continue",
        "   identities=([scope['target_identity']] if target==scope['target'] else [])+[area['members'][target] for area in self._area_payload_scopes if area['impact'] is scope and target in area['members']]\n   if not identities or self.payload_incarnation(source)!=scope['source_identity'] or any(self.payload_incarnation(target)!=identity for identity in identities):continue")
    replace(proj,"if any(cast is scope['cast'] and source==scope['source'] and target==scope['target'] for scope in self._impact_payload_scopes):return False",
        "if any(cast is scope['cast'] and source==scope['source'] for scope in self._impact_payload_scopes):return False")
    effects=OUT/'ark_sim/domains/effects.py'
    replace(effects,'import math','import math\nfrom contextlib import nullcontext')
    replace(effects,'                for child in effect["effects"]:\n                    self.execute(source, members, child, ability, cast, area_cause)',
        '                projectile=getattr(self.ctx,"projectiles",None)\n                scope=projectile.payload_area(source,cast,members) if projectile is not None else nullcontext()\n                with scope:\n                    for child in effect["effects"]:\n                        self.execute(source, members, child, ability, cast, area_cause)')
    changes={str(p.relative_to(OUT)):{'base_sha':sha(BASE/p.relative_to(OUT)),'sha':sha(p)} for p in (OUT/'ark_sim').rglob('*')
        if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts and p.read_bytes()!=(BASE/p.relative_to(OUT)).read_bytes()}
    assert len(changes)==2
    target=ROOT/'validation/campaign/retained_area_payload_v16/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'parent_core':core(BASE),'core':core(OUT),'changes':changes,
        'scope':'Actual area members added only inside original packet cast lineage; source and every overlapping target incarnation held through child effects; independent proof pending'}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='changes'}))


if __name__=='__main__':main()
