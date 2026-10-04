"""Fix optional-domain compatibility in a new identity; frozen v1 unchanged."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT.parent/'unpack_work/campaign_elemental_v1_candidate'
OUT=ROOT.parent/'unpack_work/campaign_elemental_v2_candidate'
OLD_CORE='838ce3cc2cb019f91f594b7a40ac999a1300b8088f4603418a3029b253186cb2'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'],cwd=root,text=True).strip()
def main():
    assert core(OLD)==OLD_CORE and not OUT.exists()
    shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    path=OUT/'ark_sim/domains/lifecycle.py';text=path.read_text(encoding='utf-8')
    before='        self.ctx.elemental.initialize(ref)'
    assert text.count(before)==1
    text=text.replace(before,"        elemental=getattr(self.ctx, 'elemental', None)\n        if elemental is not None:elemental.initialize(ref)\n        elif 'elemental' in components:raise ValueError('Elemental component requires its compiled runtime feature')")
    before='        self.ctx.elemental.cancel(ref, reason)';assert text.count(before)==1
    text=text.replace(before,"        elemental=getattr(self.ctx, 'elemental', None)\n        if elemental is not None:elemental.cancel(ref, reason)")
    path.write_text(text,encoding='utf-8',newline='')
    for filename,relative in [('api.py','ark_sim/adapters/api.py'),('capabilities.py','ark_sim/content/capabilities.py')]:
        shutil.copyfile(Path(__file__).parent/'v2_delta'/filename,OUT/relative)
    newcore=core(OUT)
    helper=ROOT/'tools/chapter09_elemental/test_author_v1.py';out=helper.with_name('test_author_v2.py')
    assert not out.exists();out.write_text(helper.read_text(encoding='utf-8').replace('campaign_elemental_v1_candidate','campaign_elemental_v2_candidate').replace('chapter09_elemental_author_v1','chapter09_elemental_author_v2'),encoding='utf-8')
    report=ROOT/'validation/campaign/chapter09_elemental_v2';report.mkdir(parents=True,exist_ok=True)
    result={'parent_candidate_core':OLD_CORE,'base_core':'82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae',
            'candidate':str(OUT),'core':newcore,'relative_parent_delta':['ark_sim/domains/lifecycle.py','ark_sim/adapters/api.py','ark_sim/content/capabilities.py'],
            'source_failure':'Legacy direct RuntimeContext did not install optional elemental system; unguarded retire access raised AttributeError.',
            'old_frozen_modified':False,'author_assertions_changed':False}
    p=report/'composition.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'core':newcore,'composition_sha':sha(p)}))

if __name__=='__main__':main()
