"""Support native-life source overlays while preserving legacy v2 validation.

Named profiles change provenance only. Definition, scene and command guards
remain mandatory; no verifier weakens source equality to count a passed report.
"""
import argparse,hashlib,json,sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from tools.campaign_runthrough_progress import ROOT,sha,births
from tools.campaign_runthrough_progress_v3 import inspect as legacy_inspect
from tools.campaign_runthrough_progress_v2 import verify_reference
from tools.chapter06_review.stage_converter_v7 import exact


def validate_native_overlay(package,parent,commands):
    p=deepcopy(package);profile=p['scenarioDraft']['metadata'].pop('runthrough_profile')
    provenance=p['manifest']['metadata'].pop('goal_base_life_authoring')
    key=profile['base_life_resource'];scene=p['scenarioDraft'];native=parent['scenarioDraft']['resources'][key]
    if type(scene['resources'][key].get('initial')) is not int or type(scene['resources'][key].get('capacity')) is not int or scene['resources'][key].get('initial')!=99999 or scene['resources'][key].get('capacity')!=99999:
        raise ValueError('Base life must be99999')
    if not exact(provenance,{'native':native,'selected_initial':99999,'selected_capacity':99999,'only_authoring':'Campaign user base life policy'}):
        raise ValueError('Native-life override provenance differs')
    scene['resources'][key]=deepcopy(native)
    if not exact(p,parent):raise ValueError('Overlay altered data beyond base life/profile/provenance')
    if not exact(profile['fixed12'],scene['roster']) or len(profile['fixed12'])!=12:
        raise ValueError('Overlay fixed12 roster differs')
    if type(profile['source_births']) is not int or type(profile['deploy_capacity']) is not int or profile['source_births']!=sum(births(scene).values()) or profile['deploy_capacity']!=scene['parameters']['deploy_capacity']:
        raise ValueError('Overlay source population/deployment limit differs')
    if profile.get('public_commands_sha256') and profile['public_commands_sha256']!=hashlib.sha256(commands.read_bytes()).hexdigest():
        raise ValueError('Named profile command pin differs')
    return profile


def inspect(root,entry):
    if entry.get('input_validation')!='native_life_public_dialogue_v1':return legacy_inspect(root,entry)
    root=Path(root);row={'process_status':'not_run','determinism_status':'pending','durable_checkpoint_status':'pending',
        'accuracy_status':'pending','accuracy_reason':'Reference policies separate from user client feedback','report':entry['report']}
    try:
        package_path=root/entry['package'];parent_path=root/entry['parent_package'];command_path=root/entry['commands'];report_path=root/entry['report']
        if not report_path.exists():row['process_status']='running_or_not_reported';return row
        package=json.loads(package_path.read_bytes());parent=json.loads(parent_path.read_bytes());commands=json.loads(command_path.read_bytes());report=json.loads(report_path.read_bytes())
        profile=validate_native_overlay(package,parent,command_path)
        if sha(parent_path)!=entry['parent_sha256']:raise ValueError('Native-life parent bytes drift')
        if report['schema']!='ark-sim/campaign-runthrough/v1' or report['package_sha256']!=sha(package_path) or report['commands_sha256']!=sha(command_path) or report['implementation']!=entry['implementation']:
            raise ValueError('Report input/core identity differs')
        if not exact(report['profile'],profile) or not exact(report['source_at_start'],report['source_at_completion']) or report['identity_stable'] is not True:
            raise ValueError('Run profile/source identity differs')
        expected=births(package['scenarioDraft']);state=report['state']
        for counter in ('kills','leaks','pending_waves'):
            if type(state[counter]) is not int or state[counter]<0:raise ValueError('Strict nonnegative battle counter required: '+counter)
        for counter in ('end_tick','terminal_tick'):
            if type(report[counter]) is not int or report[counter]<0:raise ValueError('Strict nonnegative report clock required')
        for flag in ('passed','process_complete','identity_stable','checkpoint_equal','durable_checkpoint_equal','replay_equal','public_dialogue_driver','driver_equal'):
            if type(report[flag]) is not bool:raise ValueError('Strict report proof flag required: '+flag)
        if type(state['finished']) is not bool:raise ValueError('Strict battle finished flag required')
        for section,field in ((report['journal'],'events'),(report['journal'],'bytes'),(report['observations'],'event_count')):
            if type(section[field]) is not int or section[field]<0:raise ValueError('Strict journal/observation count required')
        for name in ('continuation_journal','replayed_journal'):
            for field in ('count','bytes'):
                if type(report[name][field]) is not int or report[name][field]<0:raise ValueError('Strict continued journal count required')
        if not exact(report['expected_births'],expected) or not exact(report['actual_births'],expected):raise ValueError('Typed expected/actual births differ')
        for count in report['expected_births'].values():
            if type(count) is not int or count<0:raise ValueError('Strict source birth count required')
        from tools.campaign_public_dialogue_validation import validate as validate_dialogue
        dialogue=validate_dialogue(root,package,commands,report)
        observation=report['observations'];journal=report['journal'];p=Path(journal['path']);p=p if p.is_absolute() else root/p
        if not p.exists() or sha(p)!=journal['sha256'] or journal['events']!=observation['event_count'] or p.stat().st_size!=journal['bytes']:
            raise ValueError('Complete journal bytes/count differ')
        for name in ('continuation_journal','replayed_journal'):
            item=report[name];q=Path(item['path']);q=q if q.is_absolute() else root/q
            if item['count']!=journal['events'] or item['bytes']!=journal['bytes'] or sha(q)!=item['sha256'] or item['sha256']!=journal['sha256']:
                raise ValueError('Actual continued/replayed full journal differs')
        checkpoint=Path(report['checkpoint']);checkpoint=checkpoint if checkpoint.is_absolute() else root/checkpoint
        if sha(checkpoint)!=report['checkpoint_sha256'] or report['checkpoint_encoding']!='insertion-order JSON; loaded from actual saved bytes':
            raise ValueError('Actual durable checkpoint identity differs')
        sealed=verify_reference(root,report)
        complete=report['passed'] is True and report['process_complete'] is True and state['finished'] is True and state['pending_waves']==0 and state['timeline']['phase']=='complete' and exact(report['actual_births'],expected) and state['kills']+state['leaks']==sum(expected.values())
        deterministic=complete and report['checkpoint_equal'] is True and report['durable_checkpoint_equal'] is True and report['replay_equal'] is True
        row.update(process_status='complete' if complete else 'incomplete',determinism_status='verified' if deterministic else 'pending',
            durable_checkpoint_status='verified' if deterministic else 'pending',report_sha256=sha(report_path),implementation=report['implementation'],
            package_sha256=report['package_sha256'],end_tick=report['end_tick'],kills=state['kills'],leaks=state['leaks'],base_life_final=report['base_life_final'],
            sealed_checkpoint_journal=sealed,input_validation='native_life_public_dialogue_v1',public_dialogue=dialogue)
    except (KeyError,TypeError,ValueError,OSError) as error:row.update(process_status='stale_or_invalid',reason=str(error))
    return row


def build(root=ROOT):
    root=Path(root);registry_path=root/'validation/campaign/runthrough/registry.json';registry=json.loads(registry_path.read_bytes());catalog_path=root/'packages/campaign/mainline_catalog.json';catalog=json.loads(catalog_path.read_bytes())
    targets=sorted((s for s in catalog['stages'] if s['selected']),key=lambda s:(s['chapter'],s['native_sequence']))
    if set(registry['cases'])-{s['native_id'] for s in targets}:raise ValueError('Registered stage outside36targets')
    rows=[]
    for target in targets:
        row={k:target[k] for k in ('native_id','code','chapter')};entry=registry['cases'].get(target['native_id'])
        row.update(inspect(root,entry) if entry else {'process_status':'not_run','determinism_status':'pending','durable_checkpoint_status':'pending','accuracy_status':'pending'});rows.append(row)
    return {'schema':'ark-sim/campaign-runthrough-progress/v5','goal_status':'active','base_life':99999,'unit_hp_unchanged':True,
        'registry_sha256':sha(registry_path),'catalog_sha256':sha(catalog_path),'cases':rows,
        'counts':{'targets':len(targets),'process_complete':sum(r['process_status']=='complete' for r in rows),
            'determinism_verified':sum(r['process_status']=='complete' and r['determinism_status']=='verified' for r in rows),
            'durable_checkpoint_verified':sum(r['process_status']=='complete' and r['durable_checkpoint_status']=='verified' for r in rows),'actual_game_accuracy_verified':0}}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();result=build()
    with args.output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result['counts']))
