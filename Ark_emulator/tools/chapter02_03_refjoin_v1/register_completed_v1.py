"""Register actual full source runs after unchanged source gates and disk audit."""
import hashlib
import json
import shutil
from pathlib import Path
from tools.campaign_runthrough_progress_v5 import inspect

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'validation/campaign/chapter02_03_refjoin_v1'
CORE='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    freeze=FOLDER/'freeze.json'
    assert sha(freeze)=='41b6516c3f44ff3999c084614de928ad11f24d25a55d6036c36f187148f6c653'
    frozen=json.loads(freeze.read_bytes())
    for name,pin in frozen['evidence_artifacts'].items():assert sha(ROOT/name)==pin,name
    for group in ('author_helpers','future_runner_support'):
        for name,pin in frozen[group].items():assert sha(ROOT/name)==pin,name
    review=FOLDER/'root_independent_source_review.json'
    assert sha(review)=='9585a59e0f52d86a03bd36d22c389c1cb5d8a581ed686b835deabcb79f41dc6f'
    independent=json.loads(review.read_bytes());assert independent['passed'] is True
    out=ROOT/'validation/campaign/runthrough/register_02_10_03_08_source_v1'
    out.mkdir(exist_ok=True)
    assert not (out/'registration.json').exists()
    prep=json.loads((FOLDER/'preparation.json').read_bytes());cases={};results={}
    final_pins={'02-10':'fefe64c33e0aadb9af71fcdddd67e4f7a5a8e477e62470f472532427f9eb3ea5',
                '03-08':'5cef18d12c63405a5295da504f5c80b2510cb91e7040628f1de33c6fc16d4c7a'}
    for row in prep['results']:
        stage=row['stage'];actual=Path('E:/ArkSimEvidence/campaign')/(stage.replace('-','_')+'_8fa_refjoin_v1')/'full_v1.json'
        assert sha(actual)==final_pins[stage]
        process=FOLDER/(stage+'.root_exit.json');exit_record=json.loads(process.read_bytes())
        assert exit_record['actual_child_exit']==0 and type(exit_record['actual_child_exit']) is int
        assert exit_record['report_sha']==sha(actual)
        final=out/(stage+'.final.exact_copy.json')
        if not final.exists():shutil.copyfile(actual,final)
        assert sha(final)==sha(actual)
        full=json.loads(final.read_bytes())
        for field in ('continuation_journal','replayed_journal'):
            journal=full[field];path=Path(journal['path'])
            assert path.stat().st_size==journal['bytes'] and sha(path)==journal['sha256']
            assert journal['sha256']==full['journal']['sha256']
            assert journal['count']==full['journal']['events']
        for name,pin in full['source_at_completion'].items():assert sha(name)==pin,name
        entry={'package':str(Path(row['life_package']).relative_to(ROOT)),
               'parent_package':str(Path(row['native_package']).relative_to(ROOT)),
               'parent_sha256':row['native_sha'],'commands':str(Path(row['commands']).relative_to(ROOT)),
               'implementation':CORE,'report':str(final.relative_to(ROOT))}
        result=inspect(ROOT,entry)
        assert result['process_status']=='complete' and result['determinism_status']=='verified' and result['durable_checkpoint_status']=='verified',result
        results[stage]=result;cases['main_'+stage]=entry
        print(json.dumps({'stage':stage,'inspection':result['process_status'],'report_sha':sha(final)}),flush=True)
    registry=ROOT/'validation/campaign/runthrough/registry.json';before=registry.read_bytes();data=json.loads(before)
    old_entries={key:data['cases'].get(key) for key in cases}
    # Existing historical entries did not complete the current source gate.
    # Preserve their exact records while changing only active registry pointers.
    for key,old in old_entries.items():
        assert old is None or old['implementation']!=CORE, key
    (out/'registry.before.json').write_bytes(before);data['cases'].update(cases)
    registry.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    receipt={'passed':True,'cases':cases,'inspections':results,'historical_entries':old_entries,'registry_before_sha':hashlib.sha256(before).hexdigest(),
             'registry_after_sha':sha(registry),'independent_source_review_sha':sha(review),'source_freeze_sha':sha(freeze),
             'scope':'Actual complete fixed8fa source runs/CP700/head/full journals. Current d509 and new candidates remain different identities. Full numeric accuracy and user client feedback remain pending.'}
    p=out/'registration.json';p.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'registered':list(cases),'sha':sha(p)}))


if __name__=='__main__':main()
