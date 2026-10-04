"""Strict optional exit configuration on the corrected projectile scope core."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ORIGINAL=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v12_candidate'
EXIT=ROOT.parent/'unpack_work/campaign_exit_accounting_v1_candidate'
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v14_candidate'
OUT=ROOT.parent/'unpack_work/campaign_exit_accounting_v3_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(p,before,after):
    text=p.read_text(encoding='utf8');assert text.count(before)==1
    p.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(BASE)=='24d4041df5d997f66f3b6243e979940856fade9b3b932b31530f0f4e87cdc21a' and not OUT.exists()
    report=json.loads((ROOT/'validation/campaign/exit_accounting_v1/composition.json').read_bytes())
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for rel,pins in report['changes'].items():
        assert sha(EXIT/rel)==pins['sha']
        if pins['base_sha'] is not None:assert sha(BASE/rel)==sha(ORIGINAL/rel)==pins['base_sha']
        (OUT/rel).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(EXIT/rel,OUT/rel)
    replace(OUT/'ark_sim/content/capabilities.py',
        '        if lifecycle.get("policy"):\n            if lifecycle.get("exit_rule"):\n                require("lifecycle.exit", identifier+".lifecycle.exit_rule", [*scopes, lifecycle.get("rules", {})], lifecycle["exit_rule"])\n            require("lifecycle.death",',
        '        if lifecycle.get("exit_rule"):\n            require("lifecycle.exit", identifier+".lifecycle.exit_rule", [*scopes, lifecycle.get("rules", {})], lifecycle["exit_rule"])\n        if lifecycle.get("policy"):\n            require("lifecycle.death",')
    replace(OUT/'ark_sim/content/schemas.py',
        "        emissions=components.get('lifecycle',{}).get('death_projectiles')",
        "        lifecycle=components.get('lifecycle',{})\n        if 'exit_rule' in lifecycle:\n            if not isinstance(lifecycle['exit_rule'],str) or not lifecycle['exit_rule']: raise ContentError(identifier+': nonempty exit rule ID required')\n            if not isinstance(lifecycle.get('exit_parameters',{}),Mapping): raise ContentError(identifier+': exit parameters must be record')\n        elif 'exit_parameters' in lifecycle: raise ContentError(identifier+': exit parameters require explicit rule')\n        emissions=components.get('lifecycle',{}).get('death_projectiles')")
    value={'parent_core':core(BASE),'core':core(OUT),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'scope':'Optional exit config strictly typed and independently preflighted; source consumer remains reference model'}
    target=ROOT/'validation/campaign/exit_accounting_v3/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(value,f,indent=2)
    print(json.dumps(value))


if __name__=='__main__':main()
