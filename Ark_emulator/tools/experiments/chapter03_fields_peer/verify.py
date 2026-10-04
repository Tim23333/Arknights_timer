from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter03_fields_peer';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    import pytest
    before=implementation_digest();cases=[];inputs=[];original=Compiler.compile
    def capture(self,p,*args,**kwargs):
        path=OUT/f'input_{len(inputs):02d}.json';write(path,thaw(p));inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=capture;code=pytest.main([str(Path(__file__).with_name('test_defup.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
    from tools.experiments.chapter03_fields_peer.test_defup import fixture
    p=fixture();program=Compiler().compile(p);s=Engine.create(program,seed=3503);commands=[{'action':'skill','source':source,'ability':'ability/'+ability,'at':at} for at,source,ability in [(0,'attacker','physical'),(1,'victim','next'),(2,'attacker','physical'),(3,'victim','leave'),(4,'attacker','physical')]]
    for command in commands:s.submit({k:v for k,v in command.items() if k!='at'},at=command['at'])
    s.advance(2);cp=OUT/'public_checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(4);r.advance(4)
    assert s.ctx.resources.current('victim','hp')==8140 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
    for filename,value in [('public_input.json',p),('public_commands.json',commands),('public_replay.json',s.export_replay()),('public_final.json',s.snapshot())]:write(OUT/filename,value)
    after=implementation_digest();assert before==after
    names=['tools/build_chapter03_defup_field.py','packages/campaign/chapter03_tiles/defup.reference_model.json','packages/campaign/chapter03_plans/source.plan.json',
        'tools/experiments/chapter03_fields_peer/test_defup.py',str(Path(__file__).relative_to(ROOT))]
    report={'schema':'ark-sim/independent-defup-field-review/v1','status':'passed_declared_reference_profile','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':after,
        'source_locks':{x:sha(ROOT/x) for x in names},'cases':cases,'inputs':inputs,'public_evidence':{'checkpoint_resume_equal':True,'command_replay_equal':True,'HP':8140,
            'packets':[thaw(e) for e in s.session.events if e['type']=='damage.accepted'],'files':{str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('public*')}},
        'scope':'actual source category3/motion3 qualification, flatDEF200 compositional attribute layer, independent neighboring sources, flying token, arts unaffected, exact public CP/replay',
        'actual_client_verified':False,'whole_stage_executed':False,'formal_approved':False}
    write(OUT/'final_review.json',report);print(json.dumps({'passed':len(cases),'report_sha256':sha(OUT/'final_review.json'),'core':before}))
if __name__=='__main__':main()
