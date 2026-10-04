"""Register the completed frozen C5 run from retained post-cleanup receipts."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FINAL=Path('E:/ArkSimEvidence/campaign/05_10_8fa4e36752e92f7d/public_v1.json')
OUT=ROOT/'validation/campaign/runthrough/register_05_10_archived_v1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sys.path.insert(0,str(ROOT))
    from tools.build_campaign_runthrough_input import apply
    from tools.compare_campaign_trace import exact
    from tools.campaign_runthrough_progress import births
    assert sha(FINAL)=='24815c7b053d0e2c1c07c986c1e2fc2f0fe36e0cd0c4c943e7421a95f95fd3e2'
    report=json.loads(FINAL.read_bytes())
    assert all(report[key] is True for key in ('passed','process_complete','checkpoint_equal','durable_checkpoint_equal','replay_equal','identity_stable'))
    assert report['implementation']=='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
    assert report['source_at_start']==report['source_at_completion']
    for name,value in report['source_at_completion'].items():assert sha(name)==value,name
    package='packages/campaign/chapter05_stage_models/combined_v3/level_main_05-10.life99999.json'
    parent='packages/campaign/chapter05_stage_models/combined_v3/level_main_05-10.native_life.json'
    commands='scenarios/campaign/chapter05/level_main_05-10/combined_v3/public_fixed12.compact_v1.commands.json'
    p=json.loads((ROOT/package).read_bytes());native=json.loads((ROOT/parent).read_bytes())
    expected=apply(native,sha(ROOT/parent))
    expected['manifest']['metadata']['builder_sha256']=p['manifest']['metadata']['builder_sha256']
    assert exact(expected,p),'Only base life/source provenance overlay allowed'
    assert report['package_sha256']==sha(ROOT/package) and report['commands_sha256']==sha(ROOT/commands)
    assert report['profile']==p['scenarioDraft']['metadata']['runthrough_profile']
    assert report['expected_births']==report['actual_births']==births(p['scenarioDraft'])
    assert sum(report['actual_births'].values())==73==report['state']['kills']+report['state']['leaks']
    assert report['state']['finished'] is True and report['state']['pending_waves']==0 and report['state']['timeline']['phase']=='complete'
    public=json.loads((ROOT/commands).read_bytes());assert len(report['commands'])==len(public)==34
    for outcome,action in zip(report['commands'],sorted(public,key=lambda value:value['at'])):
        expected_action=dict(action);tick=expected_action.pop('at')
        assert outcome['time']==tick and outcome['payload']['action']==expected_action
        assert outcome['type'] in ('command.accepted','command.rejected')
    deployed={outcome['payload']['action']['entity'] for outcome in report['commands']
              if outcome['type']=='command.accepted' and outcome['payload']['action']['action']=='deploy'}
    assert len(deployed)==12
    journal=report['journal']
    assert journal['events']==report['observations']['event_count']==4343031
    assert journal['bytes']==12271020349
    for name in ('continuation_journal','replayed_journal'):
        row=report[name];assert row['sha256']==journal['sha256'] and row['bytes']==journal['bytes'] and row['count']==journal['events']
    # Raw journals were deleted by the user-authorized completion watcher.
    # Preserve their actual worker comparison result, never pretend to hash
    # those missing files again during registration.
    assert not Path(journal['path']).exists()
    numeric=ROOT/'validation/trace_audit/05-10.sealed_original_full.v6.json'
    assert sha(numeric)=='1be7e6b19737817fd8dd156d6ca07cb8823d944f539362fc71932ba62fa3c25a'
    audit=json.loads(numeric.read_bytes());assert audit['source_formula_consistent'] and audit['counts']['failed']==0
    registry_path=ROOT/'validation/campaign/runthrough/registry.json'
    before=registry_path.read_bytes();registry=json.loads(before);assert 'main_05-10' not in registry['cases']
    archive_path=ROOT/'validation/campaign/runthrough/archived_logs.receipts.v1.json'
    assert sha(archive_path)=='c2026d4489bc5e88ec769d2cc21f709e5ddf607cd83787433c2bc296411df42b'
    archive=json.loads(archive_path.read_bytes());assert len(archive['cases'])==12
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'registry.before.json').write_bytes(before);shutil.copyfile(FINAL,OUT/'final.exact_copy.json')
    entry={'package':package,'parent_package':parent,'commands':commands,'implementation':report['implementation'],
           'report':(OUT/'final.exact_copy.json').relative_to(ROOT).as_posix()}
    registry['cases']['main_05-10']=entry
    verified={'native_id':'main_05-10','code':'5-10','chapter':5,'process_status':'complete','determinism_status':'verified',
              'durable_checkpoint_status':'verified','accuracy_status':'pending_user_feedback',
              'verification_basis':'Frozen original worker completed forward/durableCP/head comparisons; retained compact receipt, raw deleted by user policy',
              'report_sha256':sha(FINAL),'implementation':report['implementation'],'package_sha256':sha(ROOT/package),
              'end_tick':11600,'kills':6,'leaks':67,'base_life_final':99931,'raw_journals_reverified_now':False}
    archive['cases']['main_05-10']={'entry':entry,'prior_verified_progress':verified,'report_sha':sha(FINAL),
        'source_sha':{field:sha(ROOT/entry[field]) for field in ('package','parent_package','commands')},
        'implementation':report['implementation'],'process_complete':True,'durable_checkpoint_equal':True,'replay_equal':True,
        'journals_recorded_by_original_validation':{name:report.get(name) for name in ('journal','continuation_journal','replayed_journal','checkpoint_sha256','checkpoint_event_reference')},
        'log_retention':'Raw deleted after real completed worker verification at user request','live_journals_reverified_here':False,'client_verified':False}
    archive['schema']='ark-sim/completed-log-archive/v2';archive['parent_archive_sha']=sha(archive_path)
    encoded=(json.dumps(registry,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    archive['registry_sha']=hashlib.sha256(encoded).hexdigest()
    new_archive=ROOT/'validation/campaign/runthrough/archived_logs.receipts.v2.json'
    assert not new_archive.exists()
    new_archive.write_bytes((json.dumps(archive,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    registry_path.write_bytes(encoded)
    receipt={'passed':True,'native_id':'main_05-10','display_code':'5-10','entry':entry,
        'report_sha':sha(FINAL),'archive_sha':sha(new_archive),'registry_before':hashlib.sha256(before).hexdigest(),
        'registry_after':sha(registry_path),'process_complete':True,'births':73,'kills':6,'leaks':67,
        'raw_rehashed_after_cleanup':False,'worker_validation_preserved':True,'client_verified':False,
        'source_formula_subset_audit_sha':sha(numeric),'all_numeric_fields_verified':False}
    (OUT/'registration.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'passed':True,'formal_complete_process':13,'archive_sha':sha(new_archive),'registration_sha':sha(OUT/'registration.json')}))


if __name__=='__main__':main()
