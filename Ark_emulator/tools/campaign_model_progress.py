"""Track all36 goals; count only current externally reviewed model receipts."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_model_acceptance import case_identity,consume_completed_stage,load,sha
from tools.campaign_progress import atomic_json,fixed_roster


def build(root=ROOT):
    root=Path(root);catalog=load(root/'packages/campaign/mainline_catalog.json')
    reference=load(root/'packages/campaign/roster.reference.json');ids=fixed_roster(reference)
    targets=sorted((row for row in catalog['stages'] if row['selected']),key=lambda r:(r['chapter'],r['native_sequence']))
    rows=[]
    for target in targets:
        native=target['native_id'];result_path=root/'validation/campaign/results_v2'/f'{native}.json'
        case_path=root/'validation/campaign/cases_v2'/f'{native}.json'
        row={'native_id':native,'code':target['code'],'chapter':target['chapter'],'model_status':'not_run','client_status':'pending'}
        if case_path.exists() and result_path.exists():
            case=load(case_path);result=load(result_path)
            try:
                if case['native_id']!=native or case['level_id']!=target['level_id']:
                    raise ValueError('Registered case belongs to different native goal')
                if case_identity(root,case,reference)!=result['input_identity']:
                    raise ValueError('Current inputs differ from the accepted model result')
                receipt=root/'validation/campaign/reviews_v2'/f'{native}.json'
                if sha(receipt)!=result['conversion_review_sha256']:
                    raise ValueError('Accepted independent receipt changed')
                validated=consume_completed_stage(root,case,reference,receipt.relative_to(root).as_posix(),result['completed_run'])
                if validated['observations']!=result['observations'] or validated['model_result']!=result['model_result']:
                    raise ValueError('Accepted result differs from current evidence')
                row.update(model_status='accepted',model_result=result['model_result'],input_identity=result['input_identity'],
                    receipt=receipt.relative_to(root).as_posix(),result=result_path.relative_to(root).as_posix())
            except (ValueError,KeyError,OSError) as error:
                row.update(model_status='stale_or_unverified',reason=str(error),historical_result=result_path.relative_to(root).as_posix())
        rows.append(row)
    return {'schema':'ark-sim/model-campaign-progress/v2','goal_status':'active','targets':len(rows),'fixed_roster':ids,
        'counts':{'targets':len(rows),'model_accepted':sum(r['model_status']=='accepted' for r in rows),
            'client_verified':0,'complete_native_operators':0},'cases':rows,
        'scope':'Current immutable battle/content/core + external semantic/scope receipts; client accuracy separate'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/progress_v2.json')
    args=parser.parse_args();d=build();atomic_json(args.output,d);print(json.dumps(d['counts']))
