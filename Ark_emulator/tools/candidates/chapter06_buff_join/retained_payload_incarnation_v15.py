"""Bind real scoped payloads to both incarnations, including pure-policy revive."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v14_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v15_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(p,before,after):
    text=p.read_text(encoding='utf8');assert text.count(before)==1,(str(p),before)
    p.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(BASE)=='24d4041df5d997f66f3b6243e979940856fade9b3b932b31530f0f4e87cdc21a' and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    life=OUT/'ark_sim/domains/lifecycle.py'
    replace(life,'        elif plan["action"] == "revive":',
        '        elif plan["action"] == "revive":\n            self.ctx.set(ref, ("runtime", "lifecycle_generation"), self.ctx.get(ref, ("runtime", "lifecycle_generation"), 0)+1)')
    proj=OUT/'ark_sim/domains/projectiles.py'
    replace(proj,' def retained_payload_allowed(self,source,target,cast):',
        ' def payload_incarnation(self,ref):\n  return (self.ctx.alive(ref),self.ctx.active(ref),self.ctx.get(ref,("runtime","state")),self.ctx.get(ref,("runtime","death_generation"),0),self.ctx.get(ref,("runtime","lifecycle_generation"),0))\n def retained_payload_allowed(self,source,target,cast):')
    replace(proj,"   if self._definition(current)['lifecycle']['source_invalid']!='retain':continue",
        "   if not self.ctx.active(source) and self._definition(current)['lifecycle']['source_invalid']!='retain':continue")
    replace(proj,"   identity=(self.ctx.alive(source),self.ctx.active(source),self.ctx.get(source,('runtime','state')),self.ctx.get(source,('runtime','death_generation'),0))\n   if identity!=scope['source_identity']:continue",
        "   if self.payload_incarnation(source)!=scope['source_identity'] or self.payload_incarnation(target)!=scope['target_identity']:continue")
    replace(proj,"  return False\n def _finish", "  if any(cast is scope['cast'] and source==scope['source'] and target==scope['target'] for scope in self._impact_payload_scopes):return False\n  return None\n def _finish")
    replace(proj,"'source_identity':(self.ctx.alive(latest['source']),self.ctx.active(latest['source']),self.ctx.get(latest['source'],('runtime','state')),self.ctx.get(latest['source'],('runtime','death_generation'),0)),",
        "'source_identity':self.payload_incarnation(latest['source']),'target_identity':self.payload_incarnation(target),")
    app=OUT/'ark_sim/domains/buff_application.py'
    replace(app,'        return ctx.active(source) or (projectile is not None and projectile.retained_payload_allowed(source,target,cast))',
        '        authority=projectile.retained_payload_allowed(source,target,cast) if projectile is not None else None\n        return ctx.active(source) if authority is None else authority')
    replace(app,"def source_identity(): return (ctx.alive(source), ctx.active(source), ctx.get(source, ('runtime', 'state')), _generation(ctx, source))\n        source_at_entry = source_identity()",
        "def identity(ref): return (ctx.alive(ref), ctx.active(ref), ctx.get(ref, ('runtime', 'state')), _generation(ctx, ref), ctx.get(ref, ('runtime', 'lifecycle_generation'), 0))\n        source_at_entry, target_at_entry = identity(source), identity(target)")
    replace(app,'source_identity() != source_at_entry','identity(source) != source_at_entry or identity(target) != target_at_entry')
    changed={str(p.relative_to(OUT)):{'base_sha':sha(BASE/p.relative_to(OUT)),'sha':sha(p)} for p in (OUT/'ark_sim').rglob('*')
        if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts and p.read_bytes()!=(BASE/p.relative_to(OUT)).read_bytes()}
    assert len(changed)==3
    target=ROOT/'validation/campaign/retained_buff_payload_v15/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'parent_core':core(BASE),'core':core(OUT),'changes':changed,
        'scope':'Scope authority checked even on active sources; both source/target live states and true policy-revive generations bound; existing non-scoped active effects retain behavior'}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='changes'}))


if __name__=='__main__':main()
