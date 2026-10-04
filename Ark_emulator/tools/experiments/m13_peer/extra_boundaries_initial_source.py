"""Peer cancellation recovery, nested RNG stop, multi-target stop and public alias."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.experiments.m13_peer import verify as h
from tools.experiments.m13_peer import fatal_paths as f


def recovered_cancel_guards():
    from ark_sim.rules.errors import RuleError
    p=h.scene(actions=[h.action('first'),h.action('second')]);other=deepcopy(p['controls'][0]);other['id']='control/fail';p['controls'].append(other)
    p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'][1]['definition']=other['id']
    p['controls'][0]['on_cancel']=[f.fatal()]
    other['on_cancel']=[{'op':'random','stream':'imp','probability':1,'on_success':[h.payment(-1)]},
        {'op':'modify_resource','target':'battle','resource':'credit','amount_rule':'rule/fail'}]
    p['rules']=[{'id':'rule/fail','kind':'calculation_rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'1/0'}}]
    s=h.make(p);s.advance(3);saved=s.checkpoint()
    try:s.ctx.controls.cancel('first','peer',policy='continue')
    except RuleError:pass
    else:raise AssertionError('cross-control cancellation did not reach source rule failure')
    assert s.checkpoint()==saved
    # The failed API call had no state impact; these real commands must work
    # and replay without needing an out-of-band guard repair.
    s.submit({'action':'control_ack','control':'first','step':0},at=3)
    s.submit({'action':'control_ack','control':'second','step':0},at=4);s.advance(4)
    assert s.ctx.resources.current('system/battle','credit')==14
    assert not s.ctx.state()['input_locks'] and not s.ctx.state()['finished']
    assert all(s.ctx.controls.instance(ref)['status']=='completed' for ref in ('first','second'))
    assert not s.session.random.samples
    return h.observed(s,{'failed_cancel_is_atomic_and_guards_restore':True,'next_legitimate_ACKs_complete_both':True,'credit14_no_failed_RNG':True})


def nested_random_terminal():
    p=h.scene(steps=[{'kind':'effects','effects':[{'op':'emit','target':'battle','event':'peer.outer','effects':[
        {'op':'random','stream':'imp','probability':1,'on_success':[f.fatal(),
            {'op':'random','stream':'imp','probability':1,'on_success':[h.payment(5)]}]},h.pulse('nested_after')]}]}],ack='immediate')
    s=h.make(p);s.advance(1)
    assert len(s.session.random.samples)==1
    assert s.ctx.controls.instance('notice')['status']=='cancelled' and s.ctx.resources.current('system/battle','credit')==10
    assert not [e for e in s.session.events if e['type'] in ('peer.nested_after','control.completed')]
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith(('domain.control','domain.timeline'))]
    return h.observed(s,{'exactly_first_RNG_draw_only':True,'terminal_stops_remaining_nested_children':True})


def multi_target_terminal():
    p=h.scene(steps=[{'kind':'effects','effects':[{'op':'damage','damage_type':'true','selector':'selector/peer_enemies',
        'rules':{'damage.pipeline':'rule/peer_life_loss'}}]}],ack='immediate')
    p['scenarioDraft']['initialEntities']=[{'definition':'unit/peer_enemy','instanceAlias':a,'position':{'row':0,'col':i}} for i,a in enumerate(('one','two'))]
    p['selectors']=[{'id':'selector/peer_enemies','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':None}]
    # Pure settlement contract allocates real target HP10 and battle life5.
    # This tests target-loop stopping without fake callbacks or actor IDs.
    p['rules']=[{'id':'rule/peer_life_loss','kind':'calculation_rule','contract':'damage.pipeline','implementation':{'type':'graph',
        'nodes':[{'id':'settled','expression':"{'accepted':True,'amount':10,'allocations':[{'target':inputs.target.id,'resource':'hp','delta':-10},{'target':inputs.source.id,'resource':'life','delta':-5}],'events':[]}"}],
        'output':'nodes.settled'}}]
    s=h.make(p);s.advance(1)
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(hits)==1 and hits[0]['payload']['target']==s.session.world.resolve('one')
    assert not s.ctx.alive('one') and s.ctx.alive('two') and s.ctx.resources.current('two','hp')==10
    assert s.ctx.controls.instance('notice')['status']=='cancelled' and s.ctx.state()['result']=='defeat'
    assert not [t for t in s.session.scheduler.pending if t['kind'].startswith(('domain.control','domain.timeline'))]
    return h.observed(s,{'first_target_real_health_and_life_allocations_terminal':True,'second_target_untouched_HP10':True,'only_one_accepted_packet':True})


def public_bad_actor_alias():
    p=h.scene();p['controls'][0]['on_start']=[]
    p['scenarioDraft']['resources']['dp']={'initial':10,'capacity':10}
    p['entities'].append({'id':'unit/peer_card','kind':'entity','tags':['player','ground'],'components':{
        'attributes':{'base':{'max_hp':100,'atk':0,'def':0,'mres':0,'block_count':0,'deploy_cost':1,'redeploy_time':1}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},
        'deployable':{'policy':'policy/ark_ground_deploy','terrain':'ground'},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']['roster']=['unit/peer_card'];s=h.make(p);s.advance(2)
    s.submit({'action':'deploy','entity':'unit/peer_card','alias':7,'position':{'row':0,'col':0}},at=2);s.advance(1)
    reject=[e for e in s.session.events if e['type']=='command.rejected']
    assert len(reject)==1 and 'alias' in reject[0]['payload']['reason']
    assert s.checkpoint()['kernel']['failure'] is None and s.ctx.resources.current('system/battle','dp')==10
    assert s.ctx.controls.instance('notice')['status']=='running'
    assert not any(e['definition_id']=='unit/peer_card' for e in s.session.world.entities())
    return h.observed(s,{'public_command_is_rejected_not_kernel_fail_stop':True,'no_actor_no_payment_no_control_change':True})


CASES={'cancel_guards_restored_and_next_commands':recovered_cancel_guards,'nested_random_terminal':nested_random_terminal,
    'multi_target_terminal':multi_target_terminal,'public_bad_actor_alias':public_bad_actor_alias}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,required=True);parser.add_argument('--digest',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();runtime=args.runtime_root.resolve();sys.path.insert(0,str(runtime));import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().parent==runtime/'ark_sim';before=implementation_digest();assert before==args.digest
    files=[Path(__file__),Path(h.__file__),Path(f.__file__)];source={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};cases=[]
    for name,fn in CASES.items():
        try:cases.append({'case':name,'result':'passed','actual':fn()})
        except Exception as error:cases.append({'case':name,'result':'failed','error':repr(error)})
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};stable=source==after and before==implementation_digest();passed=stable and all(c['result']=='passed' for c in cases)
    result={'schema':'ark-sim/bounded-control-peer-review/v1','passed':passed,'implementation_sha256':before,'runtime_module':ark_sim.__file__,
        'cases':cases,'identity_stable':stable,'source_at_start':source,'source_at_completion':after,
        'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'result':'passed' if passed else 'failed'} for p in files],
        'formal_approval':False,'promotion_receipt':False,'scope':'transaction recovery/nested RNG/multi-target/public alias boundaries only'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':passed,'cases':[(c['case'],c['result'],c.get('error')) for c in cases]}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
