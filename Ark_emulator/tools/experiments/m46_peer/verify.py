from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m46_area_members_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m46_peer';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    import pytest
    before=implementation_digest();assert before=='c4c02d6dd11b457f30d1ccd75ac2175bde332e149c20828a62481ab3a2115000'
    files=[p for p in (RUNTIME/'ark_sim').rglob('*') if p.is_file() and p.suffix in ('.py','.json')];corelocks={str(p):sha(p) for p in files}
    fixtures=[];cases=[];original=Compiler.compile
    def track(self,p,*args,**kwargs):
        path=OUT/f'fixture_{len(fixtures):02d}.json';write(path,thaw(p));fixtures.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=track;code=pytest.main([str(Path(__file__).with_name('test_area.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
    from tools.experiments.m46_peer.test_area import fixture
    public=[]
    for name in ('grid','scope'):
        p=fixture()
        if name=='scope':p['rules'][0]['implementation']={'type':'expression','expression':"[ctx.target.id] if ctx.owner.id==ctx.source.id and ctx.ability.id=='ability/area' and ctx.effect.parameters.offsets[0][0]==-1 else []"}
        program=Compiler().compile(p);s=Engine.create(program,seed=4646);commands=[{'action':'skill','source':'src','ability':'ability/area','at':3}];s.submit({k:v for k,v in commands[0].items() if k!='at'},at=3);s.advance(2)
        directory=OUT/name;directory.mkdir(exist_ok=True);path=directory/'checkpoint.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(4);r.advance(4)
        assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
        for filename,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:write(directory/filename,value)
        calculations=[thaw(e) for e in s.session.events if e['type']=='calculation' and e['payload']['calculation_id']=='area.members'];assert len(calculations)==1
        public.append({'case':name,'target_HP':{x:s.ctx.resources.current(x,'hp') for x in ('main','flycorner','outside','othercorner')},'actual_calculation':calculations,
            'checkpoint_resume_equal':True,'command_replay_equal':True,'files':{str(p.relative_to(ROOT)):sha(p) for p in directory.iterdir()}})
    after=implementation_digest();assert before==after and corelocks=={str(p):sha(p) for p in files}
    source_files=['tools/candidates/m46_area_members/prepare_candidate.py','tools/build_skulsr_reference50.py','packages/campaign/chapter02_behavior/reference50/skulsr.model.json',
        'tools/experiments/m46_peer/test_area.py',str(Path(__file__).relative_to(ROOT)),'validation/campaign/m46_area/final.json']
    report={'schema':'ark-sim/independent-area-review/v1','status':'passed_declared_model_profile','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':after,
        'core_and_catalog_source_locks':corelocks,'source_locks':{x:sha(ROOT/x) for x in source_files},'cases':cases,'actual_fixture_inputs':fixtures,'public_evidence':public,
        'fixture_errors_preserved':{'initial.log':'Unclosed independent fixture list, collection failure; no runtime conclusion.',
            'fresh.log':'Failure pipeline initially placed at target definition scope; damage.pipeline is source-owned. Corrected late explicit failure rule gives real atomic test.'},
        'scope':['projected-cell membership, custom rule/context and calculation trace','unique actual candidate ID and nonarea/wrongkind gates','ground primary separate from flight splash','map-edge half-up point policy','damage/RNG/trace atomic restoration','retired source legal scheduled propagation','old radius no new area calculation','same-core durable checkpoint and command replay'],
        'actual_client_verified':False,'whole_stage_executed':False,'formal_approved':False}
    write(OUT/'final_review.json',report);print(json.dumps({'passed':len(cases),'core':before,'report_sha256':sha(OUT/'final_review.json')}))
if __name__=='__main__':main()
