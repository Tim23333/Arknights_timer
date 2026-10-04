"""Actual public ack provenance and durable prefix validation, not fake inputs."""
import hashlib,json
from collections import Counter
from pathlib import Path
from tools.compare_campaign_trace import exact


def integer(value):
    if type(value) is not int or value<0:raise ValueError('Strict nonnegative dialogue integer required')
    return value


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def validate(root,package,commands,report):
    root=Path(root);scene=package['scenarioDraft']
    if report.get('public_dialogue_driver') is not True or report.get('driver_equal') is not True:
        raise ValueError('Actual public dialogue driver/restore proof required')
    sidecar=report['driver_checkpoint'];saved=json.loads(Path(sidecar['path']).read_bytes())
    if sha(sidecar['path'])!=sidecar['sha256']:raise ValueError('Actual driver sidecar bytes differ')
    final=report['driver_final'];keys={'policy','program','runtime','at','cursor','submitted'}
    for d in (saved,final):
        if set(d)!=keys or d['policy']!='external_dialogue_observation_plus_one_tick/v2':raise ValueError('Driver shape/policy differs')
        if d['program']!=report['program'] or d['runtime']!=report['runtime']:raise ValueError('Driver program/runtime identity differs')
        integer(d['at']);integer(d['cursor'])
    cp=Path(report['checkpoint']);cp=cp if cp.is_absolute() else root/cp;checkpoint=json.loads(cp.read_bytes())
    if saved['at']!=checkpoint['kernel']['time'] or saved['cursor']!=report['checkpoint_event_reference']['count']:
        raise ValueError('Driver actual checkpoint boundary differs')
    if final['at']!=report['end_tick'] or final['cursor']!=report['journal']['events']:
        raise ValueError('Driver final boundary differs')
    if not exact(final['submitted'][:len(saved['submitted'])],saved['submitted']):raise ValueError('Driver saved ledger is not exact final prefix')
    replaypath=Path(report['journal']['path']).with_name(Path(report['journal']['path']).name.replace('.events.jsonl','.replay.json'))
    replay=json.loads(replaypath.read_bytes())
    if replay['program_fingerprint']!=report['program'] or replay['runtime_fingerprint']!=report['runtime'] or replay['until']!=report['end_tick']:
        raise ValueError('Actual public replay identity differs')
    orders=[integer(c['order']) for c in replay['commands']]
    if orders!=list(range(1,len(orders)+1)):raise ValueError('Actual public submission orders differ')
    awaits=[];outcomes=[];activated=[];completed=[];deployed=[]
    with Path(report['journal']['path']).open(encoding='utf8') as f:
        for line in f:
            e=json.loads(line);kind=e['type']
            if kind=='control.awaiting_ack':awaits.append(e)
            if kind in ('command.accepted','command.rejected'):outcomes.append(e)
            if kind=='entity.activated':activated.append(e)
            if kind=='control.completed':completed.append(e)
            if kind=='entity.deployed':deployed.append(e)
    if not exact(outcomes,report['commands']):raise ValueError('Actual public outcomes differ from report')
    prefix_waits=[e for e in awaits if e['id']<=saved['cursor']]
    if len(saved['submitted'])!=len(prefix_waits):raise ValueError('Saved driver ledger does not cover actual checkpoint waits')
    for row,event in zip(saved['submitted'],prefix_waits):
        if row.get('event')!=event['id'] or row.get('submitted_at',saved['at']+1)>saved['at']:
            raise ValueError('Saved driver ledger crossed actual checkpoint boundary')
    if len(replay['commands'])!=len(outcomes):raise ValueError('Replay has missing or foreign public submissions')
    for submitted in replay['commands']:
        integer(submitted['order']);integer(submitted['at']);integer(submitted['submitted_at'])
        if submitted['submitted_at']>submitted['at']:raise ValueError('Replay submission after execution')
        matched=[e for e in outcomes if e['time']==submitted['at'] and exact(e['payload']['action'],submitted['action'])]
        if len(matched)!=1:raise ValueError('Public replay submission has no unique real outcome')
    if len(final['submitted'])!=len(awaits):raise ValueError('Public ledger does not cover every actual dialogue wait')
    for row,event in zip(final['submitted'],awaits):
        if set(row)!={'event','control','step','submitted_at','at'}:raise ValueError('Unknown public ledger fields')
        for k in ('event','step','submitted_at','at'):integer(row[k])
        if row['event']!=event['id'] or row['control']!=event['payload']['control'] or row['step']!=event['payload']['step']:
            raise ValueError('Ledger does not bind actual observed control wait')
        # advance_to observes after the half-open one-tick advance returns:
        # an event at t is first observed at boundary t+1, then submitted for
        # boundary+1. Time0 pre-existing waits may be observed before advance.
        if row['submitted_at'] not in (event['time'],event['time']+1) or row['at']!=row['submitted_at']+1:raise ValueError('Public one-tick observer ack timing policy differs')
        action={'action':'control_ack','control':row['control'],'step':row['step']}
        matches=[c for c in replay['commands'] if exact(c['action'],action) and c['at']==row['at'] and c['submitted_at']==row['submitted_at']]
        if len(matches)!=1:raise ValueError('Ack absent/duplicated in actual replay record')
        admitted=[e for e in outcomes if e['type']=='command.accepted' and e['time']==row['at'] and exact(e['payload']['action'],action)]
        if len(admitted)!=1:raise ValueError('Actual public ack not accepted exactly once')
    expected=[{'at':c['at'],'action':{k:v for k,v in c.items() if k!='at'}} for c in commands]
    expected += [{'at':r['at'],'action':{'action':'control_ack','control':r['control'],'step':r['step']}} for r in final['submitted']]
    if len(outcomes)!=len(expected) or Counter(json.dumps({'at':e['time'],'action':e['payload']['action']},sort_keys=True) for e in outcomes)!=Counter(json.dumps(e,sort_keys=True) for e in expected):
        raise ValueError('Missing/foreign/duplicate public command outcome')
    raw_controls=[a for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='control']
    if len(completed)!=sum(a.get('count',1) for a in raw_controls):raise ValueError('Native controls not fully completed')
    if scene['parameters']['deploy_capacity']==0:
        if deployed or any(e['payload']['action']['action']=='deploy' for e in outcomes):raise ValueError('Native zero-slot training stage acquired player deployments')
        needed=[r['registration_key'] for r in scene['initialEntities'] if r.get('active') is False]
        if Counter(e['payload']['registration_key'] for e in activated)!=Counter(needed):raise ValueError('Native NPC activations differ')
    return {'verified':True,'actual_dialogue_acks':len(awaits),'accepted_acks':len(final['submitted']),
        'durable_driver_sha':sidecar['sha256'],'native_controls_completed':len(completed),'fixed12_selected':len(scene['roster']),
        'actual_player_deployments':len(deployed),'native_predefined_activations':len(activated)}
