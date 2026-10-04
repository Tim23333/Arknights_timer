import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v13_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v14_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):
 code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
 return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)=='a532397e5f2dbd405649ce2baaad6d79938de3256d52dc52e1da9d1f79ffcdbc' and not OUT.exists()
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 file=OUT/'ark_sim/domains/projectiles.py';text=file.read_text(encoding='utf8')
 old="   if self.ctx.get(source,('runtime','death_generation'),0)!=scope['source_generation']:continue"
 new="   identity=(self.ctx.alive(source),self.ctx.active(source),self.ctx.get(source,('runtime','state')),self.ctx.get(source,('runtime','death_generation'),0))\n   if identity!=scope['source_identity']:continue"
 assert text.count(old)==1;text=text.replace(old,new)
 old="'source_generation':self.ctx.get(latest['source'],('runtime','death_generation'),0),"
 new="'source_identity':(self.ctx.alive(latest['source']),self.ctx.active(latest['source']),self.ctx.get(latest['source'],('runtime','state')),self.ctx.get(latest['source'],('runtime','death_generation'),0)),"
 assert text.count(old)==1;text=text.replace(old,new);file.write_text(text,encoding='utf8',newline='')
 out=ROOT/'validation/campaign/retained_buff_payload_v14/composition.json';out.parent.mkdir(parents=True,exist_ok=True)
 report={'core':core(OUT),'parent_core':core(BASE),'old_sha':sha(BASE/'ark_sim/domains/projectiles.py'),'new_sha':sha(file),'scope':'Impact scope binds entry source alive/active/state/incarnation across sibling application plans, not only one plan'}
 with out.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps(report))
if __name__=='__main__':main()
