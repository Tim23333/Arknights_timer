"""Register source-bound recovered CP/head results under compact log retention."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from tools.campaign_runthrough_progress_v5 import validate_native_overlay
    from tools.campaign_runthrough_progress import births
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-id',required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--report-sha',required=True);parser.add_argument('--package',required=True)
    parser.add_argument('--parent',required=True);parser.add_argument('--commands',required=True)
    parser.add_argument('--prior-archive',required=True);parser.add_argument('--prior-archive-sha',required=True)
    parser.add_argument('--new-archive',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mechanism-receipt',type=Path);parser.add_argument('--mechanism-sha')
    args=parser.parse_args();assert sha(args.report)==args.report_sha
    report=json.loads(args.report.read_bytes());recovery=report['recovery']
    assert all(report[field] is True for field in ('passed','process_complete','checkpoint_equal','durable_checkpoint_equal','replay_equal','identity_stable','driver_equal'))
    assert recovery['head_driver_equal'] is True and recovery['head_wave_conservation'] is True
    assert report['source_at_start']==report['source_at_completion']
    assert recovery['source_at_recovery_start']==recovery['source_at_recovery_completion']
    for group in (report['source_at_completion'],recovery['source_at_recovery_completion']):
        for name,value in group.items():assert sha(name)==value,name
    package=json.loads((ROOT/args.package).read_bytes());parent=json.loads((ROOT/args.parent).read_bytes())
    validate_native_overlay(package,parent,ROOT/args.commands)
    assert sha(ROOT/args.package)==report['package_sha256'] and sha(ROOT/args.commands)==report['commands_sha256']
    assert report['profile']==package['scenarioDraft']['metadata']['runthrough_profile']
    assert births(package['scenarioDraft'])==report['expected_births']==report['actual_births']
    state=report['state'];total=sum(report['actual_births'].values())
    assert state['finished'] is True and state['pending_waves']==0 and state['timeline']['phase']=='complete'
    assert total==state['kills']+state['leaks']
    actions=json.loads((ROOT/args.commands).read_bytes())
    outcomes=report['commands']
    if report['public_dialogue_driver']:
        ack=[row for row in outcomes if row['payload']['action'].get('action')=='control_ack']
        outcomes=[row for row in outcomes if row['payload']['action'].get('action')!='control_ack']
        assert ack and all(row['type']=='command.accepted' for row in ack)
        assert len(ack)==len(report['driver_final']['submitted'])
    assert len(outcomes)==len(actions)
    for observed,action in zip(outcomes,sorted(actions,key=lambda row:row['at'])):
        expected=dict(action);at=expected.pop('at')
        assert observed['time']==at and observed['payload']['action']==expected
        assert observed['type'] in ('command.accepted','command.rejected')
    assert report['journal']['events']==report['replayed_journal']['count']==report['observations']['event_count']
    # Raw head JSON dictionary key order can change through canonical replay
    # command encoding. Full source-bound observations compared every value,
    # task, RNG and event order, rather than requiring raw JSON byte equality.
    assert report['replay_equal'] is True
    assert sha(ROOT/args.prior_archive)==args.prior_archive_sha
    archive=json.loads((ROOT/args.prior_archive).read_bytes())
    registry_path=ROOT/'validation/campaign/runthrough/registry.json';before=registry_path.read_bytes();registry=json.loads(before)
    assert args.native_id not in registry['cases'] and set(registry['cases'])==set(archive['cases'])
    targets=json.loads((ROOT/'packages/campaign/mainline_catalog.json').read_bytes())['stages']
    selected=next(row for row in targets if row['native_id']==args.native_id and row['selected'])
    mechanism=None
    if args.mechanism_receipt:
        assert args.mechanism_sha and sha(args.mechanism_receipt)==args.mechanism_sha
        mechanism=json.loads(args.mechanism_receipt.read_bytes());assert mechanism['passed'] is True
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);shutil.copyfile(args.report,out/'final.exact_copy.json')
    (out/'registry.before.json').write_bytes(before)
    entry={'package':args.package,'parent_package':args.parent,'parent_sha256':sha(ROOT/args.parent),
           'commands':args.commands,'implementation':report['implementation'],'report':(out/'final.exact_copy.json').relative_to(ROOT).as_posix(),
           'input_validation':'native_life_public_dialogue_v1' if report['public_dialogue_driver'] else 'native_life_overlay_v1'}
    registry['cases'][args.native_id]=entry
    verified={'native_id':args.native_id,'code':selected['code'],'chapter':selected['chapter'],
        'process_status':'complete','determinism_status':'verified','durable_checkpoint_status':'verified',
        'accuracy_status':'pending_user_feedback','report_sha256':args.report_sha,'implementation':report['implementation'],
        'package_sha256':report['package_sha256'],'end_tick':report['end_tick'],'kills':state['kills'],'leaks':state['leaks'],
        'base_life_final':report['base_life_final'],'raw_journals_reverified_now':False,
        'verification_basis':'Frozen original completed forward/durableCP plus actual recovered public head and source guard; compact retention receipt'}
    archive['cases'][args.native_id]={'entry':entry,'prior_verified_progress':verified,'report_sha':args.report_sha,
        'source_sha':{field:sha(ROOT/entry[field]) for field in ('package','parent_package','commands')},
        'implementation':report['implementation'],'process_complete':True,'durable_checkpoint_equal':True,'replay_equal':True,
        'journals_recorded_by_original_validation':{field:report.get(field) for field in ('journal','continuation_journal','replayed_journal','checkpoint_sha256','checkpoint_event_reference')},
        'recovery_source_guard_count':len(recovery['source_at_recovery_completion']),
        'client_verified':False,'live_journals_reverified_here':False,'log_retention':'Raw removed after completed comparison by user policy'}
    archive['parent_archive_sha']=args.prior_archive_sha;archive['schema']='ark-sim/completed-log-archive/v3'
    encoded=(json.dumps(registry,ensure_ascii=False,indent=2)+'\n').encode()
    archive['registry_sha']=hashlib.sha256(encoded).hexdigest();new_archive=ROOT/args.new_archive;assert not new_archive.exists()
    new_archive.write_bytes((json.dumps(archive,ensure_ascii=False,indent=2)+'\n').encode());registry_path.write_bytes(encoded)
    receipt={'passed':True,'entry':entry,'source_births':total,'report_sha':args.report_sha,'archive_sha':sha(new_archive),
        'registry_sha':sha(registry_path),'mechanism_receipt_sha':args.mechanism_sha,'actual_game_accuracy_verified':False,
        'all_numeric_fields_verified':False,'raw_rehashed_after_cleanup':False,'completed_count':len(registry['cases'])}
    (out/'registration.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps({'passed':True,'complete_process':len(registry['cases']),'archive_sha':sha(new_archive),'registration_sha':sha(out/'registration.json')}))


if __name__=='__main__':main()
