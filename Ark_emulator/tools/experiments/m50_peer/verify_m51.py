import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));RUNTIME=ROOT.parent/'unpack_work/campaign_m51_deploy_payment_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m50_peer/m51';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def main():
    import pytest
    before=implementation_digest();assert before=='50902adad7bd99b27b4c3c2efd2d40e97458bb181d203f5b434fcd0eaa782c1f'
    cases=[];inputs=[];original=Compiler.compile
    def captured(self,p,*args,**kwargs):
        path=OUT/f'input_{len(inputs):02d}.json';write(path,thaw(p));inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_m51.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
    from tools.experiments.m50_peer.test_m51 import fixture,command
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=5111);commands=[{**command(i),'at':i} for i in range(4)]
    commands.append({'action':'withdraw','source':'widget0','at':4})
    for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
    s.advance(2);cp=OUT/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(4);r.advance(4)
    assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot() and s.ctx.resources.current('system/battle','tickets')==0
    for filename,value in [('public_input.json',p),('public_commands.json',commands),('public_final.json',s.snapshot()),('public_replay.json',s.export_replay())]:write(OUT/filename,value)
    after=implementation_digest();assert before==after
    names=['tools/experiments/m50_peer/test_m51.py',str(Path(__file__).relative_to(ROOT)),'../unpack_work/campaign_m51_deploy_payment_candidate/ark_sim/domains/deployment.py','../unpack_work/campaign_m51_deploy_payment_candidate/ark_sim/adapters/api.py']
    old=ROOT/'validation/campaign/m50_peer/original_failures.json'
    report={'schema':'ark-sim/independent-deployment-payment-review/v1','status':'passed_declared_model_profile','core_before':before,'core_after':after,'actual_module':sys.modules['ark_sim'].__file__,
        'source_locks':{x:sha(ROOT/x) for x in names},'cases':cases,'actual_input_fixtures':inputs,'old_failures':{'path':str(old.relative_to(ROOT)),'sha256':sha(old)},
        'public_case':{'checkpoint_resume_equal':True,'command_replay_equal':True,'stock':0,'files':{str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('public*')}},
        'scope':['finite quota/withdraw','shared stock and DP exact totals','actual custom bounds partial stock and DP reject','duplicate actor record reject','marker and resource outer atomic restoration','no-stock default exact and inherited partial-DP reject','owned actual cast payment claim and shared stock','missing-resource/wrong-contract preflight'],
        'noopt_state_difference':'runtime.deployment_recorded is new persistent bookkeeping, present even without stock. Numerical/default deployment policy unchanged; no claim of raw old/new World/event equality.',
        'actual_client_verified':False,'formal_approved':False,'whole_stage_executed':False}
    write(OUT/'final_review.json',report);print(json.dumps({'passed':len(cases),'core':before,'sha256':sha(OUT/'final_review.json')}))
if __name__=='__main__':main()
