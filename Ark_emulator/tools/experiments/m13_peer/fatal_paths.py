"""Independent real fatal-effect paths; old and revised candidates get new outputs."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m13_peer import verify as h


def fatal():return {'op':'modify_resource','target':'battle','resource':'life','value':0}


def probe(entry):
    p=h.scene(steps=[{'kind':'effects','effects':[h.pulse('ordinary_step')]}],ack='immediate')
    effects=[fatal(),h.payment(5),h.pulse('fatal_followup')]
    if entry=='step':p['controls'][0]['steps']=[{'kind':'effects','effects':effects}]
    else:p['controls'][0][entry]=([h.input_lock(True)] if entry=='on_start' else [])+effects
    s=h.make(p);s.advance(1)
    immediate_jobs=[dict(t) for t in s.session.scheduler.pending if t['kind'].startswith(('domain.control','domain.timeline'))]
    actual=h.observed(s,{'terminal_defeat_from_real_life0':True,'status_cancelled_no_completed':True,'no_after_fatal_effect_credit':10,'future_birth_still_pending':1})
    valid=s.ctx.state()['finished'] and s.ctx.state()['result']=='defeat' and s.ctx.controls.instance('notice')['status']=='cancelled'
    valid=valid and not [e for e in s.session.events if e['type'] in ('control.completed','peer.fatal_followup')]
    valid=valid and s.ctx.resources.current('system/battle','credit')==10 and s.ctx.state()['pending_waves']==1
    valid=valid and not immediate_jobs
    return {'case':entry,'result':'passed' if valid else 'failed','actual':actual,'immediate_terminal_jobs':immediate_jobs}


def cancellation_terminal_failure():
    from ark_sim.rules.errors import RuleError
    p=h.scene(actions=[h.action('first'),h.action('second')]);second=deepcopy(p['controls'][0]);second['id']='control/fail_cancel';p['controls'].append(second)
    p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][1]['definition']=second['id']
    p['controls'][0]['on_cancel']=[fatal(),h.pulse('post_cancel_fatal')]
    second['on_cancel']=[{'op':'random','stream':'imp','probability':1,'on_success':[h.payment(-1)]},
        {'op':'modify_resource','target':'battle','resource':'credit','amount_rule':'rule/peer_failure'}]
    p['rules']=[{'id':'rule/peer_failure','kind':'calculation_rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}}]
    s=h.make(p);s.advance(3);before=s.checkpoint();error=None
    try:s.ctx.controls.cancel('first','peer_request',policy='continue')
    except RuleError as exc:error=str(exc)
    equal=s.checkpoint()==before
    return {'case':'on_cancel_fatal_other_cancel_failure','result':'passed' if error and equal else 'failed',
        'expected':{'fatal_cancel_checks_objectives_then_cancels_other_control':True,'other_cancel_rule_failure_rolls_back_finished_controls_RNG_events_resources_jobs':True},
        'actual':{'error':error,'full_checkpoint_equal':equal,'state':s.ctx.state(),'credit':s.ctx.resources.current('system/battle','credit')},'API_only_not_command_replay':True}


def instant_registration():
    p=h.scene(steps=[{'kind':'effects','effects':[h.pulse('instant')]}],actions=[h.action('first'),h.action('second')],ack='immediate')
    s=h.make(p);s.advance(3)
    released=[e for e in s.session.events if e['type']=='timeline.control_released']
    assert len(released)==2 and all(e['payload']['blocks_fragment'] and e['payload']['blocks_wave'] for e in released)
    assert set(e['payload']['control'] for e in released)=={'control/1','control/2'}
    assert s.ctx.state()['timeline'].get('control_members',{})=={} and s.ctx.state()['timeline']['remaining_actions']==0
    assert s.ctx.state()['pending_waves']==0 and len([e for e in s.session.world.entities() if 'enemy' in e['tags']])==1
    assert s.ctx.resources.current('system/battle','credit')==14
    return {'case':'instant_member_registration_before_completion','result':'passed','actual':h.observed(s,{'both_release_events_have_original_managed_gate_flags':True,'one_birth_after_two_completions':True,'credit14':True})}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,default=h.CANDIDATE);parser.add_argument('--digest',default=h.DIGEST)
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/m13_fatal_paths_original419b.json');args=parser.parse_args()
    sys.path.insert(0,str(args.runtime_root.resolve()));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim'
    before=implementation_digest();assert before==args.digest
    files=[Path(__file__),Path(h.__file__)];source={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    cases=[probe(entry) for entry in ('on_start','step','on_complete')]+[cancellation_terminal_failure(),instant_registration()]
    stable=before==implementation_digest() and source=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    result={'schema':'ark-sim/bounded-control-peer-review/v1','passed':stable and all(c['result']=='passed' for c in cases),
        'implementation_sha256':before,'runtime_module':ark_sim.__file__,'cases':cases,'identity_stable':stable,
        'source_at_start':source,'source_at_completion':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'result':'passed' if all(c['result']=='passed' for c in cases) else 'failed'} for p in files],
        'scope':'on_start/step/on_complete fatal control effects and cross-control cancel rollback only','formal_approval':False,'promotion_receipt':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':result['passed'],'cases':[(c['case'],c['result']) for c in cases]}));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
