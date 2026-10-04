"""Close the real dormant activation placement bypass in a new revision."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m65_connectivity_boundaries_v2_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m66_connectivity_activation_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def main():
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    if core(BASE)!='a0335fbe62082864228c3f203adce085cf589e269329e12e719d30d1fcb4a1f4':raise ValueError('Frozen M65 changed')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/lifecycle.py';b=p.read_bytes()
    def edit(old,new):
        nonlocal b
        a=old.encode();c=new.encode()
        if b'\r\n' in b:a=a.replace(b'\n',b'\r\n');c=c.replace(b'\n',b'\r\n')
        if b.count(a)!=1:raise ValueError('Activation anchor changed')
        b=b.replace(a,c)
    edit("            plan = self.ctx.get(ref, ('runtime', 'activation_plan'))",'''            deployable=self.ctx.get(ref,('deployable',),{})
            if 'connectivity' in deployable:
                from .deploy_connectivity import inspect
                inspect(self.ctx,self.ctx.definition(ref),self.ctx.get(ref,('spatial','position')),deployable,entity=self.ctx.entity(ref),phase='activate')
            plan = self.ctx.get(ref, ('runtime', 'activation_plan'))''')
    edit("            self.ctx.emit('entity.activated',",'''            if 'connectivity' in deployable and self.ctx.active(ref):
                inspect(self.ctx,self.ctx.definition(ref),self.ctx.get(ref,('spatial','position')),self.ctx.get(ref,('deployable',)),entity=self.ctx.entity(ref),phase='activated')
            self.ctx.emit('entity.activated',''')
    p.write_bytes(b)
    report={'core':core(OUT),'parent':core(BASE),'changed_file':'domains/lifecycle.py','source_sha256':sha(p),
        'counterexample':'validation/campaign/m65_connectivity/dormant_activation_counterexample.json','tested':False}
    f=ROOT/'validation/campaign/m66_connectivity/composition.json';f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':main()
