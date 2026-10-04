"""Honor the same authenticated Aura qualification in queued inactive cleanup."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_content_base_v2_candidate';OLD=ROOT.parent/'unpack_work/campaign_shared_aura_v4_candidate';OUT=ROOT.parent/'unpack_work/campaign_shared_aura_v5_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(OLD)=='2b0a722954fee85e34260fc8a1cc978b451117838b71f666842c0c6dc83c77da' and not OUT.exists();shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/buffs.py';s=file.read_text(encoding='utf8');old='''                    self.remove(target, instance["id"])
                    continue''';new='''                    aura=definition.get('aura',{})
                    retained=False
                    if aura.get('lease_policy'):
                        from .shared_auras import eligible
                        retained=eligible(self,target,instance)
                    if not retained:self.remove(target, instance["id"])
                    continue''';assert s.count(old)==1;s=s.replace(old,new);file.write_text(s,encoding='utf8',newline='');before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':[p for p in before if before[p]!=after[p]],'added':sorted(set(after)-set(before)),'parent_guards':before,'candidate_guards':after,'primary_modified':False};out=ROOT/'validation/campaign/shared_aura_v1/composition_v5.json';assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'sha':sha(out)}))
if __name__=='__main__':main()
