"""Authorize Buff plans only inside a real retained projectile impact scope."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_chapter06_buff_join_v9_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v10_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(path,before,after):
    text=path.read_text(encoding='utf8');assert text.count(before)==1,(str(path),before)
    path.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(BASE)=='84ccd1edcb7978d37f41be86e0c3d4bf0e877ec30624ef34264bb1998ecea7f4' and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    projectiles=OUT/'ark_sim/domains/projectiles.py'
    replace(projectiles,"  self._inflight_hits={}","  self._inflight_hits={}\n  self._impact_payload_scopes=[]")
    anchor=' def _finish(self,x,reason,callbacks=True):'
    method=''' def retained_payload_allowed(self,source,target):
  # A public effect cannot acquire this call-stack authority by forging cast JSON.
  for scope in reversed(self._impact_payload_scopes):
   if scope['source']!=source or scope['target']!=target:continue
   current=self._get(scope['projectile'])
   if not current or current['state']!='active' or current['source']!=source:continue
   if target not in self._inflight_hits.get(scope['projectile'],[]):continue
   if self._definition(current)['policies']['source_invalid']!='retain':continue
   if self.ctx.get(source,('runtime','death_generation'),0)!=scope['source_generation']:continue
   if self.ctx.session.time!=scope['time'] or self.ctx.session._active_key!=scope['active_key']:continue
   return True
  return False
'''
    replace(projectiles,anchor,method+anchor)
    call="   self.ctx.effects.execute(latest['source'],[target],effect,latest['ability'],latest['cast'],latest['cause'])"
    scoped="""   scope={'projectile':latest['id'],'source':latest['source'],'target':target,
          'source_generation':self.ctx.get(latest['source'],('runtime','death_generation'),0),
          'time':self.ctx.session.time,'active_key':self.ctx.session._active_key}
   self._impact_payload_scopes.append(scope)
   try:self.ctx.effects.execute(latest['source'],[target],effect,latest['ability'],latest['cast'],latest['cause'])
   finally:self._impact_payload_scopes.pop()"""
    replace(projectiles,call,scoped)
    app=OUT/'ark_sim/domains/buff_application.py'
    replace(app,"    if not ctx.active(source) or not ctx.active(target): return False",
        "    def source_allowed():\n        projectile=getattr(ctx,'projectiles',None)\n        return ctx.active(source) or (projectile is not None and projectile.retained_payload_allowed(source,target))\n    if not source_allowed() or not ctx.active(target): return False")
    replace(app,"if not ctx.active(source) or not ctx.active(target) or _generation(ctx, source) != sg or _generation(ctx, target) != tg:",
                 "if not source_allowed() or not ctx.active(target) or _generation(ctx, source) != sg or _generation(ctx, target) != tg:")
    changes={str(p.relative_to(OUT)):{'parent_sha':sha(BASE/p.relative_to(OUT)),'sha':sha(p)} for p in (OUT/'ark_sim').rglob('*')
        if p.is_file() and p.suffix in {'.py','.json'} and sha(p)!=sha(BASE/p.relative_to(OUT))}
    assert len(changes)==2
    target=ROOT/'validation/campaign/retained_buff_payload_v10/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'base_core':core(BASE),'core':core(OUT),'changes':changes,'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'policy':'Actual retained impact call scope only; source retirement does not drop existing payload; no source revival/public dead cast permission',
        'scope':'Isolated candidate requires independent real projectile lifecycle tests and source module validation'}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
