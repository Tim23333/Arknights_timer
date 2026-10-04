"""Collect completed, exact-version receipts without rewriting frozen claims."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'validation/campaign/chapter09_elemental_v3'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    frozen=json.loads((BASE/'freeze.json').read_bytes());candidate=Path(frozen['candidate'])
    assert all(sha(candidate/path)==value for path,value in frozen['guards'].items())
    reports={name:json.loads((BASE/name).read_bytes()) for name in ('author.final.json','full.json','baseline.verification.json','baseline.identity.json')}
    assert reports['author.final.json']['passed'] and reports['full.json']['passed']
    assert reports['baseline.verification.json']['passed'] and reports['baseline.identity.json']['passed']
    assert reports['full.json']['core']==frozen['core'] and reports['full.json']['identity_stable']
    files=['freeze.json','author.final.json','full.json','baseline.verification.json','baseline.identity.json','provenance.note.v1.json']
    result={'schema':'ark-sim/elemental-v3-delivery/v1','core':frozen['core'],'candidate':str(candidate),
        'author_cases':reports['author.final.json']['count'],'full_cases':len(reports['full.json']['cases']),
        'author_passed':True,'full_passed':True,'baseline_passed':True,'independent_approval':False,
        'pins':{str(BASE/name):sha(BASE/name) for name in files},
        'source_freeze':{'path':str(ROOT/'packages/campaign/chapter09_source_prepare/source.freeze.v2.json'),
            'sha256':sha(ROOT/'packages/campaign/chapter09_source_prepare/source.freeze.v2.json')},
        'scope':'Generic elemental resources/packet/lifecycle mechanics; native FIRE damage effects, ELEMENT health pipeline and stage/source-unit acceptance remain separate consumers.',
        'primary_modified':False,'whole_stage_executed':False,'client_verified':False}
    out=BASE/'delivery.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    cleanup=ROOT/'tools/cleanup_simulation_logs.py'
    folders=['chapter09_elemental_full_v3','chapter09_elemental_final_v1','chapter09_elemental_final_v2','chapter09_elemental_final_v3',
             'chapter09_elemental_author_v1','chapter09_elemental_author_v2','chapter09_elemental_author_v3',
             'chapter09_elemental_counter_v2','chapter09_elemental_counter_v3','chapter09_elemental_focused_failure_v1']
    for folder in folders:
        path=Path('E:/ArkSimLogs/runs')/folder
        if path.exists():subprocess.run([sys.executable,str(cleanup),'--apply','--run-dir',str(path),'--minimum-age-minutes','0'],cwd=ROOT,check=True)
    print(json.dumps({'delivery_sha':sha(out),'core':frozen['core'],'author':result['author_cases'],'full':result['full_cases']}))

if __name__=='__main__':main()
