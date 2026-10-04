"""Preserve separate legacy runtime-active and alive filters while retaining scoped Aura self."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OLD=ROOT.parent/'unpack_work/campaign_shared_aura_v9_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v10_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(OLD)=='9665eb3ad29bfd8cf2c400e3f30d2084dca32d82d99e3b54acabef24284ec913' and not OUT.exists();shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/movement.py';s=file.read_text(encoding='utf8');old='''        def active_or_aura_self(ref):
            if self.ctx.get(ref,('runtime','active'),True):return True
            if aura_parent is None:return False
            from .shared_auras import selection_target_allowed
            return selection_target_allowed(self.ctx,source,ref,definition,aura_parent)''';new='''        def aura_self(ref):
            if aura_parent is None:return False
            from .shared_auras import selection_target_allowed
            return selection_target_allowed(self.ctx,source,ref,definition,aura_parent)
        def runtime_active_or_aura_self(ref):
            return self.ctx.get(ref,('runtime','active'),True) or aura_self(ref)
        def active_or_aura_self(ref):
            return self.ctx.active(ref) or aura_self(ref)''';assert s.count(old)==1;s=s.replace(old,new).replace('and active_or_aura_self(e["id"]) and not self.ctx.route_hidden(e["id"])]','and runtime_active_or_aura_self(e["id"]) and not self.ctx.route_hidden(e["id"])]');file.write_text(s,encoding='utf8',newline='');before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':[p for p in before if before[p]!=after[p]],'added':sorted(set(after)-set(before)),'parent_guards':before,'candidate_guards':after,'primary_modified':False};out=ROOT/'validation/campaign/shared_aura_v1/composition_v10.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
