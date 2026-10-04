"""Finalize existing prepared one-file candidate using portable relative paths."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';OUT=ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};assert set(before)==set(after);changed=[p for p in before if before[p]!=after[p]];assert changed==['ark_sim/domains/buff_application.py'];assert core(BASE)=='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b';r={'core':core(OUT),'parent_core':core(BASE),'candidate':str(OUT),'changed':changed,'parent_guards':before,'candidate_guards':after,'initial_build_windows_separator_assertion_failure_preserved':True,'source_primary_modified':False};out=ROOT/'validation/campaign/infinite_buff_plan_v2/composition.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'composition_sha':sha(out),'one_file':changed}))
if __name__=='__main__':main()
