"""Keep reviewed exit deltas on the latest retained-source freshness core."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v12_candidate'
EXIT=ROOT.parent/'unpack_work/campaign_exit_accounting_v1_candidate'
BASE=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v13_candidate'
OUT=ROOT.parent/'unpack_work/campaign_exit_accounting_v2_candidate'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def core(root):
    code='import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'
    return subprocess.check_output([sys.executable,'-c',code,str(root)],cwd=root,text=True).strip()


def main():
    assert core(BASE)=='a532397e5f2dbd405649ce2baaad6d79938de3256d52dc52e1da9d1f79ffcdbc'
    assert core(EXIT)=='bebcc4b16bd8f6b431af048e90d58a311d629a22c73e73d805c54980156544f6' and not OUT.exists()
    report=json.loads((ROOT/'validation/campaign/exit_accounting_v1/composition.json').read_bytes())
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for rel,pins in report['changes'].items():
        src=EXIT/rel;assert sha(src)==pins['sha']
        if pins['base_sha'] is not None:assert sha(BASE/rel)==sha(OLD/rel)==pins['base_sha']
        dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    assert sha(OUT/'ark_sim/domains/buff_application.py')==sha(BASE/'ark_sim/domains/buff_application.py')
    target=ROOT/'validation/campaign/exit_accounting_v2/composition.json';target.parent.mkdir(parents=True,exist_ok=True)
    value={'parent_core':core(BASE),'core':core(OUT),'source_exit_core':core(EXIT),'catalog_sha':sha(OUT/'ark_sim/rules/contracts.json'),
        'copied_exit_changes':report['changes'],'scope':'Exact generic exit deltas on source-state freshness core; independent proof pending'}
    with target.open('x',encoding='utf8') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:v for k,v in value.items() if k!='copied_exit_changes'}))


if __name__=='__main__':main()
