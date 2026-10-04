"""Report pinned completed history after explicit raw-log retention cleanup."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.campaign_runthrough_progress_v5 import inspect as live_inspect
ARCHIVE=ROOT/'validation/campaign/runthrough/archived_logs.receipts.v1.json'
ARCHIVE_SHA='c2026d4489bc5e88ec769d2cc21f709e5ddf607cd83787433c2bc296411df42b'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archived(root,identifier,entry):
    if not ARCHIVE.exists() or sha(ARCHIVE)!=ARCHIVE_SHA:
        return None
    record=json.loads(ARCHIVE.read_bytes())['cases'].get(identifier)
    if record is None or record['entry']!=entry:
        return None
    assert sha(root/entry['report'])==record['report_sha']
    for field,value in record['source_sha'].items():
        assert sha(root/entry[field])==value
    row=dict(record['prior_verified_progress'])
    row.update(log_retention='deleted_after_completed_verification',
               raw_journals_available=False, raw_journals_reverified_now=False,
               archived_receipt_sha=ARCHIVE_SHA,
               verification_basis='Pinned historical complete-process and durableCP/head receipts; raw files removed at user request')
    return row


def build(root=ROOT):
    root=Path(root)
    registry_path=root/'validation/campaign/runthrough/registry.json'
    registry=json.loads(registry_path.read_bytes())
    catalog_path=root/'packages/campaign/mainline_catalog.json'
    catalog=json.loads(catalog_path.read_bytes())
    targets=sorted((value for value in catalog['stages'] if value['selected']),key=lambda value:(value['chapter'],value['native_sequence']))
    rows=[]
    for target in targets:
        row={key:target[key] for key in ('native_id','code','chapter')}
        entry=registry['cases'].get(target['native_id'])
        if entry:
            previous=archived(root,target['native_id'],entry)
            row.update(previous if previous is not None else live_inspect(root,entry))
        else:
            row.update(process_status='not_run',determinism_status='pending',durable_checkpoint_status='pending',accuracy_status='pending')
        rows.append(row)
    return {'schema':'ark-sim/campaign-runthrough-progress/v6','goal_status':'active',
            'base_life':99999,'unit_hp_unchanged':True,'registry_sha256':sha(registry_path),
            'catalog_sha256':sha(catalog_path),'cases':rows,
            'counts':{'targets':len(rows),'process_complete':sum(row['process_status']=='complete' for row in rows),
                      'determinism_verified':sum(row['process_status']=='complete' and row['determinism_status']=='verified' for row in rows),
                      'durable_checkpoint_verified':sum(row['process_status']=='complete' and row['durable_checkpoint_status']=='verified' for row in rows),
                      'actual_game_accuracy_verified':0}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();value=build()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps(value['counts']))
