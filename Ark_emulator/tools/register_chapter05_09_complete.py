"""Independent actual full-journal registration; never relabel old-core evidence."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.campaign_runthrough_progress_v3 import inspect,build


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main():
    private=ROOT/'validation/campaign/chapter05_public_v3/05-09.complete.private_receipt.json'
    assert sha(private)=='00fdd5b8aa165fe3740f422ac064c925c5c46c15e6279df141ed3bed1eb3d9c6'
    receipt=json.loads(private.read_bytes());assert receipt['actual_exit']==0
    reportpath=Path(receipt['exact_repo_copy']);assert sha(reportpath)==receipt['final_sha']=='02cc466f654a0e030a355f3cfcfacaab3be5b486be2f1b28de47316a0280d7c2'
    assert sha(Path(receipt['E_final']))==sha(reportpath)
    report=json.loads(reportpath.read_bytes())
    entry={'package':'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.life99999.json',
        'parent_package':'packages/campaign/chapter05_stage_models/combined_v3/level_main_05-09.native_life.json',
        'commands':'scenarios/campaign/chapter05/level_main_05-09/combined_v3/public_fixed12.compact_v1.commands.json',
        'implementation':receipt['core'],'report':str(reportpath.relative_to(ROOT))}
    result=inspect(ROOT,entry)
    assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified'
    journal=report['journal'];assert journal['events']==1937246 and journal['bytes']==3311263690
    verified={}
    for name in ['journal','continuation_journal','replayed_journal']:
        value=report[name];path=Path(value['path']);assert path.is_absolute()
        assert sha(path)==value['sha256']==journal['sha256']=='7d566e1e36b8c46a0c0aa160e0539a75857037a1a2bc873fe5620ac908d32501'
        assert path.stat().st_size==value['bytes']==journal['bytes']
        assert value.get('events',value.get('count'))==journal['events']
        verified[name]={'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size}
    checkpoint=Path(report['checkpoint']);assert sha(checkpoint)==report['checkpoint_sha256']
    registry=ROOT/'validation/campaign/runthrough/registry.json';before=registry.read_bytes();r=json.loads(before)
    assert 'main_05-09' not in r['cases']
    out=ROOT/'validation/campaign/runthrough/register_05_09_20261004';assert not out.exists();out.mkdir(parents=True)
    (out/'registry.before.json').write_bytes(before)
    r['cases']['main_05-09']=entry;registry.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    progress=build(ROOT)
    assert progress['counts']['process_complete']==progress['counts']['determinism_verified']==progress['counts']['durable_checkpoint_verified']==7
    (out/'progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='')
    target=out/'registration.json'
    with target.open('x',encoding='utf8') as f:json.dump({'passed':True,'entry':entry,'inspection':result,'actual_triple_journals':verified,
        'report_sha':sha(reportpath),'registry_before_sha':hashlib.sha256(before).hexdigest(),'registry_after_sha':sha(registry),
        'counts':progress['counts'],'scope':'Whole-process/disk/head only; numerical source coverage and user client feedback remain separate'},f,indent=2)
    print(json.dumps({'passed':True,'counts':progress['counts'],'sha':sha(target)}))


if __name__=='__main__':main()
