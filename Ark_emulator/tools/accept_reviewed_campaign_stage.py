"""Compose independent receipts only after whole-stage and all scope gates pass."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_model_acceptance import (SEMANTIC_CHECKS,case_identity,consume_completed_stage,
    load,sha,review_gate)
from tools.campaign_progress import atomic_json,object_identity


def prepare(root,preparation):
    data=load(preparation)
    if data.get('passed') is not True or data.get('whole_stage_ready') is not True:
        raise ValueError('Whole-stage validation has not completed; do not issue a receipt')
    case=data['case'];contract=load(root/case['planned_contract'])
    roster=load(root/'packages/campaign/roster.reference.json')
    if data['contract_sha256']!=sha(root/case['planned_contract']):
        raise ValueError('Reviewed preparation contract is stale')
    inputs=case_identity(root,case,roster)
    if data['content_sha256']!=inputs['content_sha256'] or data['commands_sha256']!=inputs['commands_sha256']:
        raise ValueError('Prepared battle input changed')
    source_ref=contract['semantic_source_review']
    receipt={'schema':'ark-sim/external-model-review/v2','status':'approved_for_model_run',
        'native_id':case['native_id'],'case':case,'input_identity':inputs,
        'reviewer':'root:independent-composition-of-source-scope-and-completed-stage',
        'checks':{key:'passed' for key in SEMANTIC_CHECKS},'source_reviews':[source_ref],
        **data['receipt_inputs'],
        'approval_scope':'Declared model profile only; no native/client accuracy claim',
        'preparation_sha256':sha(preparation)}
    stage_refs=receipt.get('stage_evidence',[])
    if len(stage_refs)!=1:raise ValueError('Exactly one current complete-stage artifact required')
    return case,roster,receipt,stage_refs[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    case,roster,receipt,stage_ref=prepare(ROOT,args.preparation.resolve())
    # Validate through a temporary receipt before publishing the current pointer.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix='campaign_receipt_',dir=ROOT/'validation/campaign') as directory:
        path=Path(directory)/'review.json';atomic_json(path,receipt)
        relative=path.relative_to(ROOT).as_posix()
        review_gate(ROOT,case,roster,relative)
        result=consume_completed_stage(ROOT,case,roster,relative,stage_ref)
    if args.check_only:
        print(json.dumps({'validated':True,'native_id':case['native_id'],'write_performed':False}))
        return
    receipt_path=ROOT/'validation/campaign/reviews_v2'/f"{case['native_id']}.json"
    result_path=ROOT/'validation/campaign/results_v2'/f"{case['native_id']}.json"
    case_path=ROOT/'validation/campaign/cases_v2'/f"{case['native_id']}.json"
    for path,value in [(receipt_path,receipt),(result_path,result)]:
        if path.exists():
            old=load(path);history=path.parent/'history'/case['native_id']/(object_identity(old)+'.json')
            if not history.exists():atomic_json(history,old)
        atomic_json(path,value)
    # Revalidate the persisted review and retain the actual resulting review SHA.
    persisted=consume_completed_stage(ROOT,case,roster,receipt_path.relative_to(ROOT).as_posix(),stage_ref)
    persisted['case']=case
    atomic_json(result_path,persisted)
    atomic_json(case_path,case)
    print(json.dumps({'accepted':True,'native_id':case['native_id'],'receipt':str(receipt_path),
        'result':str(result_path),'client_status':'pending'}))


if __name__=='__main__':main()
