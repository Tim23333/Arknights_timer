"""Seal fresh independent evidence and source fullbusy event assertions."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    base=ROOT/'packages/campaign/chapter08_consumers/special/bsnake_combat_independent_v1';report=base/'report.json';r=json.loads(report.read_bytes())
    module=ROOT/r['module'];assert sha(module)==r['module_sha256']=='8cd126780034884300a9ec387aabb39c47fd48fd2b8aaf9a32ffb90a5a27aa73'
    native=ROOT/'packages/campaign/chapter08_consumers/bsnake/source.closure.v1.json';assert sha(native)==r['source_sha256']
    author=ROOT/'validation/campaign/chapter08_bsnake_combat_final_v1/freeze/freeze.json';assert sha(author)=='29eb34c3bde7510a00f761f8e25b9a56075d5765d747c561cdc72ada0066bf30'
    n=json.loads(native.read_bytes());expected={case:[70,205] for case in ('phase0_def','phase1_live')};expected['ASPD2']=[35,103,171];actual={}
    for case,times in expected.items():
        vals=[]
        with (base/case/'events.jsonl').open(encoding='utf8') as f:
            for line in f:
                e=json.loads(line)
                if e['type']=='ability.finished' and e['payload']['ability'].startswith('ability/ch8/bsnake/normal/'):vals.append(e['time'])
        assert vals==times;actual[case]=vals
    assert n['frames']['Attack_A']['duration']['frame']==n['frames']['Attack_B']['duration']['frame']==70
    locks=json.loads(module.read_bytes())['manifest']['metadata']['source_locks']
    for path,pin in locks.items():assert sha(Path(path))==pin,path
    files=[p for p in base.rglob('*') if p.is_file()]+[module,native,author,ROOT/'tools/chapter08_special/bsnake_combat_peer_v1.py',Path(__file__),ROOT/'tools/chapter08_bsnake_combat/policies_v1.py',ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v12.joint.json']
    out=base/'freeze.json';assert not out.exists()
    result={'status':'11_fresh_independent_source_policy_cases_passed','core':r['core'],'module_sha256':sha(module),'report_sha256':sha(report),'pins':{str(p):sha(p) for p in files},
        'full_busy_actual_events':actual,'scope':'Normal modes0/1 and source-dependent protection with D12 target/source flags, complete diskCP and head event equality. No author fixtures/tests/expected imported. Public reborn attribute fixture proves live1155 with original770 base; firstdown HP37500/fullRebirth, complete mode transition/skills arbitration and whole stage remain separate integration gates.',
        'source_policy_limits':['HATRED_DES tie newest actualID and strict blocker mapping are declared reference; native selection method body unavailable','ASPD clamp .01 and source float32 frame quantization are source-reference clock policies','Actual native immune12 preserved; unimmune containers explicitly distinct fixture IDs'],
        'generic_kernel_approval':False,'whole_stage_approval':False,'client_verified':False}
    out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'pins':len(result['pins'])}))
if __name__=='__main__':main()
