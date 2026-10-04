"""Register source-corrected native story after actual independent driver gate."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.append(str(ROOT))
from tools.campaign_runthrough_progress_v5 import inspect,build


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--driver-review',type=Path,required=True);ap.add_argument('--driver-review-sha',required=True);a=ap.parse_args()
    if sha(a.driver_review)!=a.driver_review_sha:raise ValueError('Independent driver inspection bytes differ')
    driver=json.loads(a.driver_review.read_bytes())
    if not driver.get('cases') or any(c.get('passed') is not True for c in driver['cases']) or driver.get('guards_equal') is not True or driver['guards_start']!=driver['guards_end']:raise ValueError('Independent driver cases/identity gate not passed')
    for path,pin in driver['guards_end'].items():
        if sha(path)!=pin:raise ValueError('Independent driver source at completion changed '+path)
    pins={'source_area':('validation/campaign/chapter06_source_area_independent/verification.json','d97c6e81e1c0b5adbca03eb9de8ebfdd4b820c2ea5dce8cb7780bef673b52174'),
        'source_blood':('validation/campaign/chapter06_story_timer_independent/verification.json','4a3dcb22cb64e8f01ec135cd563be53ff6f9645dc81bd9311e2a7cd28c0fd812'),
        'primary':('validation/campaign/content_base_v2_primary/promotion.json','f88c65b20a9c1fcb1054f8e48b68f549be29526e27b2bd1bdf8f33c9170befe3'),
        'process':('validation/campaign/chapter06_story_complete_pending_v3/verified_process.json','421e0d5a1afbe0b3bfd2095b1d5b5a7f63487be3837291793c245c9771ae4c66')}
    for _,(rel,pin) in pins.items():
        if sha(ROOT/rel)!=pin:raise ValueError('Independent source/process proof bytes differ '+rel)
    report=ROOT/'validation/campaign/chapter06_story_complete_pending_v3/full.final.exact_copy.json'
    if sha(report)!='1fcff3b7db51d85c1d71e9d2dbd7a9755c790221b9d6e7987efec6ca4b31783a':raise ValueError('Final story report changed')
    entry={'package':'validation/campaign/chapter06_story_join_v3/06-15.life99999.json',
        'parent_package':'validation/campaign/chapter06_story_join_v3/06-15.native.json',
        'parent_sha256':'29f3ab58c4e5fccdc0e3c0d65c062fb38ba82af618ce89a030b8fe62e70f2be1',
        'commands':'scenarios/campaign/chapter06/level_main_06-15/native_story_v1/commands.json',
        'implementation':'d509afe2cdd941dbaa75f4bb0cfa931b7869b29eff6753a7a571d0ef39f116d1',
        'report':str(report.relative_to(ROOT)),'input_validation':'native_life_public_dialogue_v1'}
    result=inspect(ROOT,entry)
    if result['process_status']!='complete' or result['determinism_status']!='verified' or result['durable_checkpoint_status']!='verified':raise ValueError(result)
    registry=ROOT/'validation/campaign/runthrough/registry.json';before=registry.read_bytes();r=json.loads(before)
    if 'main_06-15' in r['cases']:raise ValueError('Existing story case must not be overwritten')
    out=ROOT/'validation/campaign/runthrough/register_06_17_source_v1';out.mkdir(exist_ok=False)
    (out/'registry.before.json').write_bytes(before);r['cases']['main_06-15']=entry
    registry.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    progress=build(ROOT)
    if progress['counts']['process_complete']!=8:raise ValueError('Unexpected campaign completion count')
    (out/'progress.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    receipt={'passed':True,'entry':entry,'inspection':result,'source_gates':pins,'driver_review_sha':a.driver_review_sha,
        'registry_before_sha':hashlib.sha256(before).hexdigest(),'registry_after_sha':sha(registry),'counts':progress['counts'],
        'scope':'Whole source story process/durableCP/head/publicdriver with native0slots fixed12 selection exception; numerical unknowns and user client feedback remain separate.'}
    file=out/'registration.json';file.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'counts':progress['counts'],'sha':sha(file)}))


if __name__=='__main__':main()
