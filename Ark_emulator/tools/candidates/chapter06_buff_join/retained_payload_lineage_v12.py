import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v11_candidate'
OUT=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v12_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):
 code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
 return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)=='b0c9511d5fe1f425f82d69554927645732e9ff5792082d5c2086bbf5870bfc1a' and not OUT.exists()
 shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 file=OUT/'ark_sim/domains/projectiles.py';text=file.read_text(encoding='utf8')
 changes=[('def retained_payload_allowed(self,source,target):','def retained_payload_allowed(self,source,target,cast):'),
          ("if scope['source']!=source or scope['target']!=target:continue","if scope['source']!=source or scope['target']!=target or cast is not scope['cast']:continue"),
          ("scope={'projectile':latest['id'],'source':latest['source'],'target':target,","scope={'projectile':latest['id'],'source':latest['source'],'target':target,'cast':latest['cast'],")]
 for old,new in changes:
  assert text.count(old)==1; text=text.replace(old,new)
 file.write_text(text,encoding='utf8',newline='')
 app=OUT/'ark_sim/domains/buff_application.py';text=app.read_text(encoding='utf8')
 for old,new in [('def execute(system, source, target, effect, cause=None):','def execute(system, source, target, effect, cause=None, cast=None):'),
                 ('projectile.retained_payload_allowed(source,target)','projectile.retained_payload_allowed(source,target,cast)')]:
  assert text.count(old)==1;text=text.replace(old,new)
 app.write_text(text,encoding='utf8',newline='')
 effects=OUT/'ark_sim/domains/effects.py';text=effects.read_text(encoding='utf8');old='execute(self, source, target, effect, cause)';new='execute(self, source, target, effect, cause, cast=cast)';assert text.count(old)==1;effects.write_text(text.replace(old,new),encoding='utf8',newline='')
 out=ROOT/'validation/campaign/retained_buff_payload_v12/composition.json';out.parent.mkdir(parents=True,exist_ok=True)
 report={'core':core(OUT),'parent_core':core(BASE),'old_sha':sha(BASE/'ark_sim/domains/projectiles.py'),'new_sha':sha(file),'scope':'Actual packet cast object lineage within real impact scope; synchronous new callbacks cannot inherit launch authority; independent tests pending'}
 with out.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
 print(json.dumps(report))
if __name__=='__main__':main()
