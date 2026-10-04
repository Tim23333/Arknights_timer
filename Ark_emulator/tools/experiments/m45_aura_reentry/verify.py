from pathlib import Path
import sys,json,hashlib,difflib,subprocess
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));RUNTIME=ROOT.parent/'unpack_work/campaign_m45_aura_reentry_candidate';BASE=ROOT.parent/'unpack_work/campaign_m42_aura_remove_candidate';sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m45_aura_reentry';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def source(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*.py')}
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k!='runtime_fingerprint'}
    if isinstance(v,list):return [clean(x) for x in v]
    return v
def main():
    import pytest
    before=implementation_digest();parent=source(BASE/'ark_sim');candidate=source(RUNTIME/'ark_sim');fixtures=[];cases=[];original=Compiler.compile
    def tracked(self,p,*args,**kwargs):
        value={'input':thaw(p),'positional_options':thaw(list(args)),'keyword_options':thaw(kwargs)};path=OUT/f'fixture_{len(fixtures):02d}.json';write(path,value);fixtures.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=tracked;code=pytest.main([str(ROOT/'tools/experiments/m45_aura_reentry/test_reentry.py'),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
    from tools.experiments.m45_aura_reentry.test_reentry import fixture,hit_fixture
    public=[]
    for name in ('retire','move'):
        p=hit_fixture()
        if name=='retire':p['buffs'][1]['on_remove']=[{'op':'retire','target':'source','parameters':{'reason':'withdraw'}}]
        else:
            p['scenarioDraft']['map']['cols']=7;p['abilities'][0]['activation']['on_start'][0]['position']['col']=4;p['buffs'][1]['on_remove']=[{'op':'move','target':'source','position':{'row':0,'col':6}}]
        program=Compiler().compile(p);s=Engine.create(program,seed=4510);commands=[{'action':'skill','source':'a','ability':'ability/leave','at':3}]
        s.submit({k:v for k,v in commands[0].items() if k!='at'},at=3);s.advance(2);directory=OUT/name;directory.mkdir(exist_ok=True);cp=directory/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(4);r.advance(4)
        assert s.ctx.resources.current('b','hp')==10 and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
        for filename,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:write(directory/filename,value)
        public.append({'case':name,'target_HP':10,'checkpoint_resume_equal':True,'command_replay_equal':True,'files':{str(path.relative_to(ROOT)):sha(path) for path in directory.iterdir()}})
    comparisons=[]
    for name in ('stable','random'):
        p=fixture()
        if name=='random':p['selectors'][0].update(ordering='random',limit=1,parameters={'random_stream':'imp'})
        ip=OUT/f'{name}_input.json';cmd=OUT/f'{name}_commands.json';write(ip,p);write(cmd,[{'action':'skill','source':'a','ability':'ability/leave','at':3}])
        for runtime,label in [(BASE,'parent'),(RUNTIME,'candidate')]:subprocess.run([sys.executable,str(Path(__file__).with_name('capture_values.py')),str(runtime),str(ip),str(cmd),str(OUT/f'{name}_{label}.json')],check=True,cwd=ROOT)
        a=json.loads((OUT/f'{name}_parent.json').read_bytes());b=json.loads((OUT/f'{name}_candidate.json').read_bytes());assert clean(a['snapshot'])==clean(b['snapshot']) and clean(a['checkpoint'])==clean(b['checkpoint'])
        comparisons.append({'case':name,'full_snapshot_and_checkpoint_equal_except_runtime_fingerprint':True,'program_fingerprint_equal':a['snapshot']['program_fingerprint']==b['snapshot']['program_fingerprint'],
            'event_count':len(a['snapshot']['events']),'identity_exclusions':['runtime_fingerprint'],'source_core':a['core'],'candidate_core':b['core']})
    after=implementation_digest();assert before==after and parent==source(BASE/'ark_sim') and candidate==source(RUNTIME/'ark_sim')
    patch=[];changes=[]
    for name,h in candidate.items():
        if h!=parent.get(name):
            changes.append({'path':name,'parent_sha256':parent.get(name),'candidate_sha256':h});patch+=list(difflib.unified_diff((BASE/'ark_sim'/name).read_text(encoding='utf8').splitlines(True),(RUNTIME/'ark_sim'/name).read_text(encoding='utf8').splitlines(True),fromfile='a/ark_sim/'+name,tofile='b/ark_sim/'+name))
    (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8')
    old=ROOT/'validation/campaign/m42_peer/retire_samecast_original_failure.json'
    report={'schema':'ark-sim/aura-reentry-candidate/v1','status':'passed_declared_model_profile','candidate_root':str(RUNTIME),'actual_module':sys.modules['ark_sim'].__file__,
        'core_before':before,'core_after':after,'parent_core':'2746020dd269241d8802551ea63cb28243755ff0105a19bb09033c448f497420','source_unchanged':True,
        'cases':cases,'actual_fixtures':fixtures,'public_case_evidence':public,'normal_compatibility':comparisons,'changes':changes,'patch_sha256':sha(OUT/'candidate.patch'),
        'tool_source_locks':{str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')},
        'compatibility_logs':{str(OUT/name):sha(OUT/name) for name in ('compatibility.log','defdrn_compatibility.log')},
        'original_counterexample':{'path':str(old.relative_to(ROOT)),'sha256':sha(old)},'formal_approved':False,'actual_client_verified':False,'whole_stage_executed':False}
    write(OUT/'candidate_final.json',report);print(json.dumps({'core':before,'tests':len(cases),'report_sha256':sha(OUT/'candidate_final.json'),'patch_sha256':report['patch_sha256']}))
if __name__=='__main__':main()
