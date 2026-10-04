import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));RUNTIME=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter03_boss'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def main():
    import pytest
    before=implementation_digest();cases=[];inputs=[];original=Compiler.compile
    def captured(self,p,*args,**kwargs):
        path=OUT/f'input_{len(inputs):02d}.json';write(path,thaw(p));inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=captured;code=pytest.main([str(Path(__file__).with_name('test_boss.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
    from tools.experiments.chapter03_boss.test_boss import fixture
    public=[]
    for kind in ('normal','phase'):
        p=fixture(kind=='normal');program=Compiler().compile(p);s=Engine.create(program,seed=3813);commands=[]
        if kind=='phase':
            commands=[{'action':'skill','source':'director','ability':'ability/hp14999','at':3},{'action':'skill','source':'director','ability':'ability/hp15000','at':5}]
            for c in commands:s.submit({k:v for k,v in c.items() if k!='at'},at=c['at'])
        s.advance(2);directory=OUT/kind;directory.mkdir(exist_ok=True);cp=directory/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(24);r.advance(24)
        assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
        for name,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:write(directory/name,value)
        public.append({'case':kind,'checkpoint_resume_equal':True,'command_replay_equal':True,'files':{str(p.relative_to(ROOT)):sha(p) for p in directory.iterdir()}})
    check=subprocess.run([sys.executable,'tools/build_chapter03_boss.py','--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0
    after=implementation_digest();assert before==after
    names=['tools/build_chapter03_boss.py','packages/campaign/chapter03_models/skulsr.level1.reference.json','packages/campaign/chapter03_sources/native.reference.json','packages/campaign/chapter02_behavior/reference50/skulsr.model.json','tools/experiments/chapter03_boss/test_boss.py',str(Path(__file__).relative_to(ROOT))]
    report={'schema':'ark-sim/chapter03-level1-boss-review/v1','status':'passed_declared_reference_profile','actual_module':sys.modules['ark_sim'].__file__,'core_before':before,'core_after':after,
        'source_locks':{n:sha(ROOT/n) for n in names},'cases':cases,'actual_input_fixtures':inputs,'public_evidence':public,'build_check_stdout':check.stdout,
        'source_bindings':{'HP':30000,'ATK':1300,'DEF':240,'RES':30,'initial_half_threshold':15000,'phase':'exact source BB ratio.5 times observed effective capacity, not a literal5250/15000'},
        'scope':['distinct namespace sourcelevel1 rebinding','strict50% and restore equality','maxHP override40000 and effective modifier capacity15000 feedback cases','HP0 no mode loop','source f14/17 normal338 and low507 ATKscale packets before DEF','source leak loss2 versus entity count1','exact CP/replay under M48'],
        'client_verified':False,'formal_approved':False,'whole_stage_executed':False}
    write(OUT/'final_review.json',report);print(json.dumps({'passed':len(cases),'sha256':sha(OUT/'final_review.json'),'module_sha256':sha(ROOT/names[1]),'core':before}))
if __name__=='__main__':main()
