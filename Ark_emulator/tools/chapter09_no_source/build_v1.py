"""Isolated generic fixed no-source ARTS/PHYSICAL and NORMAL request extension."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT.parent/'unpack_work/campaign_no_source_types_v1_candidate'
PARENT='82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from ark_sim.adapters.api import implementation_digest
    assert implementation_digest()==PARENT and not OUT.exists()
    shutil.copytree(ROOT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    path=OUT/'ark_sim/domains/no_source_damage.py'
    text=path.read_text();old="""    if effect.get('damage_type') != 'true' or type(effect.get('attack_type')) is not str or effect.get('attack_type') not in {'NONE','BUFF'}:
        raise ValueError('No-source protocol requires PURE true damage and attack_type NONE or BUFF')"""
    new="""    if type(effect.get('damage_type')) is not str or effect['damage_type'] not in {'true','arts','physical'}:
        raise ValueError('No-source protocol requires an explicit supported damage type')
    if type(effect.get('attack_type')) is not str or effect['attack_type'] not in {'NONE','BUFF','NORMAL'}:
        raise ValueError('No-source protocol requires attack_type NONE, BUFF or NORMAL')"""
    assert text.count(old)==1
    path.write_bytes(text.replace(old,new).encode('utf8'))
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    core=subprocess.check_output([sys.executable,'-c',code,str(OUT)],cwd=OUT,text=True).strip()
    before={str(p.relative_to(ROOT/'ark_sim')):sha(p) for p in (ROOT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
    after={str(p.relative_to(OUT/'ark_sim')):sha(p) for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
    assert [name for name in before if before[name]!=after[name]]==['domains\\no_source_damage.py']
    receipt=ROOT/'validation/campaign/chapter09_no_source_types_v1/build.json';receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps({'parent':PARENT,'core':core,'before':before,'after':after,
        'scope':'Pure no-source request types and NORMAL attack metadata; target pipeline formulas remain explicit and replaceable',
        'required':['own full suite and baseline','independent fixed damage/no-source/SPrecovery/death/rollback checks'],
        'whole_stage':False,'promoted':False},indent=2)+'\n',encoding='utf8')
    # Keep the existing full runner offline JSON fixture; no V1 runtime import.
    source=ROOT/'ark_emulator/levels/packs/level_main_00-01.json'
    target=OUT/'ark_emulator/levels/packs/level_main_00-01.json';target.parent.mkdir(parents=True);shutil.copyfile(source,target)
    print(json.dumps({'core':core,'changed_files':1,'main_changed':False}))


if __name__=='__main__':
    sys.path.insert(0,str(ROOT));main()
