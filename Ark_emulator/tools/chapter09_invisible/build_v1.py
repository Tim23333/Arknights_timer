"""Isolated backwards-compatible optional invisible qualification."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT.parent/'unpack_work/campaign_invisible_v1_candidate'
PARENT='5c729384f50e078bd3d3ac9d211360b17bc486588770914efe92ef5b4e983826'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 sys.path.insert(0,str(ROOT));from ark_sim.adapters.api import implementation_digest
 parent=implementation_digest();assert parent==PARENT and not OUT.exists()
 shutil.copytree(ROOT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 path=OUT/'ark_sim/domains/selection.py';source=path.read_text(encoding='utf8')
 source=source.replace('SWITCHES = (','''# Optional additions preserve legacy defaults, required fields and insertion order.
OPTIONAL_BOOLS = {"invisible", "can_select_invisible"}
BOOLS = BOOLS | OPTIONAL_BOOLS
FIELDS = FIELDS | OPTIONAL_BOOLS
SWITCHES = (''',1)
 source=source.replace('            elif value: result[key]=True','''            elif key in OPTIONAL_BOOLS:
                result.setdefault(key, False)
                if value: result[key]=True
            elif value: result[key]=True''',1)
 source=source.replace('    if not immunity_declared:result.pop("abnormal_immunes", None)','''    # INVISIBLE9 is distinct from CAMOUFLAGE17 and TARGET_FREE2.
    # Do not inject new false keys into legacy readonly calculation inputs.
    if 9 in flags: result["invisible"] = True
    if not immunity_declared:result.pop("abnormal_immunes", None)''',1)
 source=source.replace('    return {"accepted":True,"reason":"eligible_declared_profile"}','''    if t.get("invisible",False) and not s.get("can_select_invisible",False): return no("invisible")
    return {"accepted":True,"reason":"eligible_declared_profile"}''',1)
 path.write_bytes(source.encode('utf8'))
 core=subprocess.check_output([sys.executable,'-c','from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'],cwd=OUT,text=True).strip()
 before={str(p.relative_to(ROOT/'ark_sim')):sha(p) for p in (ROOT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')};after={str(p.relative_to(OUT/'ark_sim')):sha(p) for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')};assert [k for k in before if before[k]!=after[k]]==['domains\\selection.py']
 receipt=ROOT/'validation/campaign/chapter09_invisible/build.v1.json';receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps({'parent':parent,'core':core,'before':before,'after':after,'changed_files':['domains/selection.py'],'main_changed':False,'promoted':False,'client_verified':False},indent=2)+'\n',encoding='utf8')
 target=OUT/'ark_emulator/levels/packs/level_main_00-01.json';target.parent.mkdir(parents=True);shutil.copyfile(ROOT/'ark_emulator/levels/packs/level_main_00-01.json',target)
 print(json.dumps({'parent':parent,'core':core,'changed_files':1}))
if __name__=='__main__':main()
