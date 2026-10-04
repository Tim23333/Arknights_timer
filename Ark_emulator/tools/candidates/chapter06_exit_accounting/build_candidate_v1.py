"""Optional pure exit accounting; source flags stay in content rules."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v12_candidate'
OUT=ROOT.parent/'unpack_work/campaign_exit_accounting_v1_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def replace(path,before,after):
    text=path.read_text(encoding='utf8');assert text.count(before)==1,(str(path),before)
    path.write_text(text.replace(before,after),encoding='utf8',newline='')


def main():
    assert core(BASE)=='6192789537ba5250da2cd781f6583a8b7ce7dccfcfba4a5bb9fc5f535674d419' and not OUT.exists()
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    runtime=Path(__file__).with_name('exit_accounting.py');shutil.copyfile(runtime,OUT/'ark_sim/domains/exit_accounting.py')
    replace(OUT/'ark_sim/domains/lifecycle.py','    def exit(self, ref):\n        params =',
        '    def exit(self, ref):\n        if self.ctx.get(ref, ("lifecycle", "exit_rule")):\n            from .exit_accounting import execute\n            return execute(self, ref)\n        params =')
    replace(OUT/'ark_sim/content/schemas.py','"lifecycle": {"policy",', '"lifecycle": {"exit_rule", "exit_parameters", "policy",')
    replace(OUT/'ark_sim/content/compiler.py',
        '"ruleset": {"ruleset"}, "recovery_rule":',
        '"ruleset": {"ruleset"}, "exit_rule": {"rule", "calculation_rule"}, "recovery_rule":')
    replace(OUT/'ark_sim/content/compiler.py',
        '"active_rule": "buff.applicability",',
        '"exit_rule": "lifecycle.exit", "active_rule": "buff.applicability",')
    replace(OUT/'ark_sim/content/capabilities.py',
        '            require("lifecycle.death",',
        '            if lifecycle.get("exit_rule"):\n                require("lifecycle.exit", identifier+".lifecycle.exit_rule", [*scopes, lifecycle.get("rules", {})], lifecycle["exit_rule"])\n            require("lifecycle.death",')
    catalog=OUT/'ark_sim/rules/contracts.json';data=json.loads(catalog.read_bytes())
    assert not any(c['id']=='lifecycle.exit' for c in data['contracts'])
    data['contracts'].append({'id':'lifecycle.exit','kind':'calculation','owner':'target',
        'inputs':[{'name':'entity','type':'entity_snapshot','required':True}, {'name':'exit','type':'record','required':True},
                  {'name':'exit_parameters','type':'record','required':True}],
        'outputType':'record','implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False,
        'description':'Optional explicit base-life and scenario accounting for a real exit; does not emit combat death.'})
    catalog.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    changed={str(p.relative_to(OUT)):{'base_sha':sha(BASE/p.relative_to(OUT)) if (BASE/p.relative_to(OUT)).exists() else None,'sha':sha(p)}
        for p in (OUT/'ark_sim').rglob('*') if p.is_file() and p.suffix in {'.py','.json'} and '__pycache__' not in p.parts
        and (not (BASE/p.relative_to(OUT)).exists() or p.read_bytes()!=(BASE/p.relative_to(OUT)).read_bytes())}
    report={'base_core':core(BASE),'core':core(OUT),'catalog_sha':sha(catalog),'changes':changed,
        'scope':'Isolated optional generic rule; training source consumer and independent proof pending'}
    target=ROOT/'validation/campaign/exit_accounting_v1/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='changes'}))


if __name__=='__main__':main()
