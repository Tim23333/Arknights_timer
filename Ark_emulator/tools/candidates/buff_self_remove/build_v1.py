"""Self-removal is an existing-instance action, not recursive construction."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
OUT=ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert core(BASE)=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a' and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    file=OUT/'ark_sim/content/dependencies.py';text=file.read_text(encoding='utf8')
    old='''                elif name in REFERENCE_KEYS or name.endswith("_rule"):
                    if isinstance(child, str):
                        result.add(child)'''
    new='''                elif name in REFERENCE_KEYS or name.endswith("_rule"):
                    if isinstance(child, str):
                        # Remove only the already-instantiated current Buff;
                        # construction/apply edges remain real dependencies.
                        if not (name == "buff" and item.get("op") == "remove_buff" and child == value.get("id") and value.get("kind") == "buff"):
                            result.add(child)'''
    assert text.count(old)==1;file.write_text(text.replace(old,new),encoding='utf8',newline='')
    target=ROOT/'validation/campaign/buff_self_remove_v1/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    report={'core':core(OUT),'parent_core':core(BASE),'changed':{'file':'content/dependencies.py','old_sha':sha(BASE/'ark_sim/content/dependencies.py'),'sha':sha(file)},
        'scope':'Exact current-buff remove reference only; arbitrary/apply cycles still rejected. Independent/compiler/schema tests pending'}
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
