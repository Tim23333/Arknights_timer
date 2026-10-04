"""Actual cross-module cooldown/connectivity/record-reentry behavior."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'
CORE='1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8'
OUT=ROOT/'validation/campaign/m68_cross';sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import write_canonical,observations,export_events
from tools.experiments.m69_connectivity.test_connectivity import fixture


def main():
    import ark_sim
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim' and implementation_digest()==CORE
    guards=[Path(__file__),ROOT/'tools/experiments/m69_connectivity/test_connectivity.py',RUNTIME/'ark_sim/domains/deployment.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};p=fixture();p['entities'][0]['components']['deployable'].update(cooldown_start='deploy',cooldown_seconds=5)
    commands=[{'at':0,'action':'deploy','definition':'unit/barrier','alias':'first','position':{'row':0,'col':1}},
        {'at':149,'action':'deploy','definition':'unit/barrier','alias':'early','position':{'row':0,'col':2}},
        {'at':150,'action':'deploy','definition':'unit/barrier','alias':'seal','position':{'row':1,'col':1}},
        {'at':151,'action':'withdraw','source':'first'},
        {'at':152,'action':'deploy','definition':'unit/barrier','alias':'second','position':{'row':1,'col':1}}]
    program=Compiler().compile(p);s=Engine.create(program,seed=68059)
    for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
    s.advance(120);OUT.mkdir(parents=True,exist_ok=True);cp=OUT/'checkpoint.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin));s.advance(60);r.advance(60)
    assert s.ctx.state()['deployments']['unit/barrier']=={'count':2,'ready_at':302}
    assert s.ctx.resources.current('system/battle','cards')==3 and s.ctx.resources.current('system/battle','dp')==7
    rejected=[e for e in s.session.events if e['type']=='command.rejected'];assert [(e['time'],e['payload']['reason']) for e in rejected]==[(149,'on_cooldown'),(150,'sealed_route:original')]
    assert s.ctx.active('second') and not s.ctx.active('first')
    observed=observations(s);assert observed==observations(r)==observations(replay(program,s.export_replay()))
    for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('snapshot.json',s.snapshot())]:write_canonical(OUT/name,value)
    journal=export_events(OUT/'events.jsonl',s)
    # API instrumentation separately verifies a nested record callback cannot
    # double-deduct cards while evaluating the new connectivity contract.
    from ark_sim.domains.deployment import prepare,record
    t=Engine.create(program,seed=68060);plan=prepare(t.ctx,'unit/barrier',{'row':0,'col':1})
    actor=t.ctx.lifecycle.create('unit/barrier',{'row':0,'col':1},deployed=True);saved=t.checkpoint();actual_calc=t.ctx.calc;calls=[]
    def nested(calculation,*args,**kwargs):
        if calculation=='deploy.connectivity' and kwargs.get('extra',{}).get('placement_phase')=='record':
            calls.append('attempt')
            try:record(t.ctx,actor,plan)
            except ValueError as error:assert 'already recorded' in str(error)
            else:raise AssertionError('Nested record accepted')
        return actual_calc(calculation,*args,**kwargs)
    t.ctx.calc=nested;record(t.ctx,actor,plan);assert calls==['attempt']
    assert t.ctx.resources.current('system/battle','cards')==4 and t.ctx.state()['deployments']['unit/barrier']['count']==1
    write_canonical(OUT/'nested.before.json',saved);write_canonical(OUT/'nested.after.json',t.checkpoint())
    after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in guards};assert before==after and implementation_digest()==CORE
    write_canonical(OUT/'final_review.json',{'schema':'ark-sim/deploy-cooldown-connectivity-cross/v1','passed':True,'core_start':CORE,'core_end':implementation_digest(),'source_start':before,'source_end':after,
        'public_commands':commands,'end_tick':180,'observations':observed,'journal':journal,'durable_checkpoint_equal':True,'replay_equal':True,'checkpoint_sha256':pin,
        'expected_ready':302,'expected_cards':3,'api_nested_record_attempts':1,'api_nested_duplicate_accepted':False,'api_scope_has_public_replay':False,
        'whole_stage_executed':False,'actual_client_verified':False})
    print(json.dumps({'passed':True,'public_end':180,'ready':302,'cards':3,'nested_record_rejected':True}))


if __name__=='__main__':main()
