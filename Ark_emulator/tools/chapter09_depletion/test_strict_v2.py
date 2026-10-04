"""Actual coherent-metadata tamper and direct-dispatch regression probes."""
import sys,json,copy,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter09_depletion.test_depletion_v2 import *
def baseline():
    s=sim();zero(s);s.session.advance(1);return s,cp(s)
def locate(checkpoint):return next(e for e in checkpoint['kernel']['world']['entities'] if e['definition_id']=='unit/depletion/target')['components']['runtime']['depletion']
def rejected(s,altered):
    try:Engine.restore(s.program,altered,providers=registry())
    except (ValueError,KeyError,IndexError):return
    raise AssertionError('Tampered checkpoint accepted')
def due_and_rehashed_time():
    s,checkpoint=baseline();altered=copy.deepcopy(checkpoint);lease=locate(altered)['lease'];row=lease['actions']['1'];row['due']=2;next(t for t in altered['kernel']['scheduler']['tasks'] if t['id']==row['task'])['at']=2;rejected(s,altered)
    issued=altered['kernel']['events']['records'][row['issued_event']-1];issued['payload']['due']=2;timing=altered['kernel']['events']['records'][row['time_event']-1];timing['payload']['value']=2;timing['payload']['trace']['value']=2;timing['payload']['trace']['raw']=2
    rejected(s,altered)
def key_slot_done_stage():
    s,checkpoint=baseline()
    for field,value in [('key','begin'),('done',True),('phase',0),('seq',999)]:
        changed=copy.deepcopy(checkpoint);lease=locate(changed)['lease'];row=lease['actions']['1'];row[field]=value;issued=changed['kernel']['events']['records'][row['issued_event']-1];issued['payload'][field]=value
        if field=='done':row['executed_event']=lease['actions']['0']['executed_event'];changed['kernel']['scheduler']['tasks']=[t for t in changed['kernel']['scheduler']['tasks'] if t['id']!=row['task']]
        if field in ('phase','seq'):next(t for t in changed['kernel']['scheduler']['tasks'] if t['id']==row['task'])[field]=value
        rejected(s,changed)
    changed=copy.deepcopy(checkpoint);locate(changed)['stage']='ready';rejected(s,changed)
    changed=copy.deepcopy(checkpoint);lease=locate(changed)['lease'];lease['actions']['2']=lease['actions'].pop('1');rejected(s,changed)
def direct_dispatch_and_incarnation():
    s=sim();zero(s);owner=s.session.world.resolve('target');before=cp(s);s.ctx.depletion._dispatch(owner,1,'1');assert cp(s)==before and s.ctx.depletion.state(owner)['stage']=='damaged'
    s.ctx.set(owner,('runtime','lifecycle_generation'),2);s.session.advance(61);assert s.ctx.depletion.state(owner)['stage']=='damaged' and not any(x['definition']=='buff/depletion/candead' for x in s.ctx.buffs._instances(owner))
def source_request_plan_tamper():
    s,checkpoint=baseline()
    for key,value in [('source',None),('health_before',10),('operation','resource_change')]:
        changed=copy.deepcopy(checkpoint);lease=locate(changed)['lease'];lease['provenance'][key]=value;changed['kernel']['events']['records'][lease['started_event']-1]['payload']['provenance'][key]=value;rejected(s,changed)
    changed=copy.deepcopy(checkpoint);lease=locate(changed)['lease'];lease['plan']['stage']='ready';changed['kernel']['events']['records'][lease['plan_event']-1]['payload']['value']['stage']='ready';rejected(s,changed)
def main():
    result=[];guard=implementation_digest()
    for name,fn in [('due_queue_and_issued_timing_coherent_tamper_rejected',due_and_rehashed_time),('key_slot_done_phase_sequence_stage_tamper_rejected',key_slot_done_stage),('direct_dispatch_due_and_owner_incarnation_no_borrow',direct_dispatch_and_incarnation),('full_provenance_and_plan_coherent_tamper_rejected',source_request_plan_tamper)]:
        try:fn();result.append({'case':name,'passed':True})
        except Exception as error:result.append({'case':name,'passed':False,'error':str(error),'traceback':traceback.format_exc()})
    report={'core':implementation_digest(),'core_before':guard,'core_after':implementation_digest(),'guard_equal':guard==implementation_digest(),'actual_exit':0 if all(x['passed'] for x in result) else 1,'results':result,'scope':'Author strict domain regressions; no comparison fields removed, coherent metadata changes still rejected'};(OUT/'author.strict.v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
