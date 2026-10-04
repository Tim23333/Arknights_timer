"""Register actual completed receipts only after legacy registry guards finish."""
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.campaign_runthrough_progress_v3 import inspect,build


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def main():
    registry=ROOT/'validation/campaign/runthrough/registry.json'
    proofpath=ROOT/'validation/campaign/runthrough/02_09_m52_v20_recovered_full_20261004.json'
    proof=json.loads(proofpath.read_bytes());current=json.loads(registry.read_bytes())
    assert proof['passed'] and proof['checkpoint_equal'] and proof['durable_checkpoint_equal'] and proof['replay_equal'] and proof['identity_stable']
    recovery=proof['recovery'];assert recovery['source_start']==recovery['source_end']
    expected=recovery['source_start'][str(registry.resolve())]
    assert sha(registry)==expected,'Registry changed before guarded recovery completed'
    for phase in ('continuation','replay'):
        receipt=proofpath.with_suffix('.'+phase+'.json');d=json.loads(receipt.read_bytes())
        assert d['equal'] and d['observations']==proof['observations'] and d['original_sha']==recovery['original_sha256']
    nextcases=current['cases'].copy()
    two=dict(nextcases['main_02-09']);two['report']=str(proofpath.relative_to(ROOT))
    fourproof=json.loads((ROOT/'validation/campaign/chapter04_10_full_v1/root_completed_inspect.json').read_bytes())
    four=fourproof['entry']
    checks={}
    for name,entry in [('main_02-09',two),('main_04-10',four)]:
        result=inspect(ROOT,entry)
        assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified',result
        checks[name]={'entry':entry,'inspection':result}
    nextcases['main_02-09']=two;nextcases['main_04-10']=four
    predicted=[inspect(ROOT,entry) for entry in nextcases.values()]
    assert sum(row['process_status']=='complete' for row in predicted)==6
    out=ROOT/'validation/campaign/runthrough/register_after_v20_20261004';assert not out.exists();out.mkdir(parents=True)
    before=registry.read_bytes();(out/'registry.before.json').write_bytes(before)
    updated={**current,'cases':nextcases};registry.write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    result=build(ROOT)
    assert result['counts']['process_complete']==result['counts']['determinism_verified']==result['counts']['durable_checkpoint_verified']==6
    (out/'progress.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    receipt={'passed':True,'registry_before_sha':hashlib.sha256(before).hexdigest(),'registry_after_sha':sha(registry),
             'v20_report_sha':sha(proofpath),'new_checks':checks,'counts':result['counts'],'scope':'Actual old-core receipts; no migration to current main core/client approval'}
    target=out/'registration.json'
    with target.open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({'passed':True,'counts':result['counts'],'sha':sha(target)}))


if __name__=='__main__':main()
