import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v10_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v11_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):
 code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
 return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)=='38de0b0570ed01c73abff5187b6ac1a99dcb31bd8aadd1ee43de10297c4f60f4' and not OUT.exists()
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 file=OUT/'ark_sim/domains/projectiles.py';text=file.read_text(encoding='utf8');old="self._definition(current)['policies']['source_invalid']";new="self._definition(current)['lifecycle']['source_invalid']";assert text.count(old)==1;file.write_text(text.replace(old,new),encoding='utf8',newline='')
 out=ROOT/'validation/campaign/retained_buff_payload_v11/composition.json';out.parent.mkdir(parents=True,exist_ok=True)
 report={'core':core(OUT),'parent_core':core(BASE),'old_sha':sha(BASE/'ark_sim/domains/projectiles.py'),'new_sha':sha(file),'scope':'Compiled projectile lifecycle field repair only; actual impact/provenance peer tests pending'}
 with out.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps(report))
if __name__=='__main__':main()
