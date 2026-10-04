"""Freeze owned M41 tests, actual input fixtures, source and patch identities."""
from pathlib import Path
import hashlib,json,subprocess,sys,difflib
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
RUNTIME=ROOT.parent/'unpack_work/campaign_m41_hole_contact_candidate';BASE=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/m41_hole';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root):return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in ('.py','.json')}
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in {'runtime_fingerprint','rule_fingerprint','program_fingerprint'}}
    if isinstance(v,list):return [clean(x) for x in v]
    return v
def main():
    import pytest
    before=implementation_digest();basefiles=files(BASE/'ark_sim');candidatefiles=files(RUNTIME/'ark_sim');fixtures=[];cases=[]
    original=Compiler.compile
    def tracked(self,scenario,*args,**kwargs):
        raw=thaw(scenario);name=f'fixture_{len(fixtures):03d}.json';path=OUT/name;path.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        fixtures.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'expected_acceptance':'see pytest case outcome; rejection fixtures retained'})
        return original(self,scenario,*args,**kwargs)
    Compiler.compile=tracked
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    code=pytest.main([str(ROOT/'tools/experiments/m41_hole/test_contact.py'),'-q'],plugins=[Results()]);Compiler.compile=original
    if code:raise SystemExit(code)
    check=subprocess.run([sys.executable,str(ROOT/'tools/experiments/m41_hole/build_profile.py'),'--check'],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0,check.stderr
    (OUT/'profile_check.log').write_text(check.stdout+check.stderr,encoding='utf8')
    for runtime,name in [(BASE,'parent'),(RUNTIME,'candidate')]:
        subprocess.run([sys.executable,str(ROOT/'tools/experiments/m41_hole/no_contact_capture.py'),str(runtime),str(OUT/f'no_contact_{name}.json')],cwd=ROOT,check=True)
    a=json.loads((OUT/'no_contact_parent.json').read_bytes());b=json.loads((OUT/'no_contact_candidate.json').read_bytes())
    same=clean(a['snapshot'])==clean(b['snapshot'])
    # Checkpoint carries implementation/API identity legitimately; compare all persistent runtime partitions directly.
    cp_keys=[k for k in a['checkpoint'] if k not in {'api','identity','runtime_fingerprint','rule_fingerprint','program_fingerprint'}]
    cp_differences=[k for k in cp_keys if clean(a['checkpoint'][k])!=clean(b['checkpoint'][k])]
    comparison={'snapshot_semantic_equal':same,'checkpoint_partition_differences':cp_differences,'identity_exclusions':['runtime_fingerprint','rule_fingerprint','program_fingerprint'],
        'parent_core':a['core'],'candidate_core':b['core'],'events_parent':len(a['snapshot']['events']),'events_candidate':len(b['snapshot']['events']),
        'scope':'one public no-contact command input; not a whole-stage equivalence claim'}
    (OUT/'no_contact_comparison.json').write_text(json.dumps(comparison,indent=2)+'\n',encoding='utf8');assert same,comparison
    from tools.experiments.m41_hole.test_contact import fixture
    public=[]
    for name in ('move','push','motion','birth'):
        value=fixture();commands=[];split=2;end=9
        if name in ('move','push'):commands=[{'action':'skill','source':'a','ability':'ability/'+name,'at':3}];split=4 if name=='push' else 2
        elif name=='motion':
            value['scenarioDraft']['initialEntities'][0].update(position={'row':0,'col':1},components={'spatial':{'motion_mode':1}})
            commands=[{'action':'skill','source':'a','ability':'ability/ground','at':3}]
        else:
            value['buffs']=[{'id':'buff/born','kind':'buff','duration_seconds':1.5,'contact_flags':{'defer_fall':True}}]
            value['entities'][0]['components']['buffs']={'initial':['buff/born']};value['scenarioDraft']['initialEntities'][0]['position']={'row':0,'col':1};split=44;end=48
        directory=OUT/('public_'+name);directory.mkdir(exist_ok=True)
        (directory/'input.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        (directory/'commands.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf8')
        program=Compiler().compile(value);s=Engine.create(program,seed=4150)
        for command in commands:s.submit({k:v for k,v in command.items() if k!='at'},at=command['at'])
        s.advance(split);cp=directory/'checkpoint.ordered.json';receipt=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,receipt));s.advance(end-split);r.advance(end-split)
        rep=s.export_replay();again=replay(program,rep)
        assert s.snapshot()==r.snapshot()==again.snapshot() and not s.ctx.alive('a')
        (directory/'replay.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        (directory/'final.json').write_text(json.dumps(s.snapshot(),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        public.append({'case':name,'actual_seed':4150,'program_fingerprint':program.fingerprint,'runtime_fingerprint':s.runtime_fingerprint,
            'checkpoint_tick':split,'end_tick':end,'checkpoint_resume_equal':True,'command_replay_equal':True,
            'kills':s.ctx.state()['kills'],'leaks':s.ctx.state()['leaks'],'HP':s.ctx.resources.current('a','hp'),
            'files':{str(p.relative_to(ROOT)):sha(p) for p in directory.iterdir() if p.is_file()}})
    changes=[];patch=[]
    for name,h in candidatefiles.items():
        if basefiles.get(name)!=h:
            changes.append({'path':name,'before':basefiles.get(name),'after':h})
            old=(BASE/'ark_sim'/name).read_text(encoding='utf8').splitlines(True) if name in basefiles else []
            new=(RUNTIME/'ark_sim'/name).read_text(encoding='utf8').splitlines(True)
            patch.extend(difflib.unified_diff(old,new,fromfile='a/ark_sim/'+name,tofile='b/ark_sim/'+name))
    (OUT/'candidate.patch').write_text(''.join(patch),encoding='utf8');after=implementation_digest()
    assert before==after and basefiles==files(BASE/'ark_sim') and candidatefiles==files(RUNTIME/'ark_sim')
    report={'schema':'ark-sim/candidate-review/v1','status':'passed_declared_math_profile','candidate_root':str(RUNTIME),'actual_module':sys.modules['ark_sim'].__file__,
        'core_before':before,'core_after':after,'source_unchanged':True,'base_core':a['core'],'cases':cases,'actual_fixture_inputs':fixtures,'changes':changes,
        'profile_path':'packages/campaign/chapter02_tiles/m41.hole.profile.json','profile_sha256':sha(ROOT/'packages/campaign/chapter02_tiles/m41.hole.profile.json'),
        'public_case_evidence':public,'contract_count':len(s.ctx.rules.catalog['contracts']),
        'tool_source_locks':{str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob('*.py')},
        'patch_sha256':sha(OUT/'candidate.patch'),'no_contact_comparison':comparison,'client_verified':False,'whole_stage_executed':False,'formal_approved':False}
    (OUT/'candidate_final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'core':before,'passed':len(cases),'report_sha256':sha(OUT/'candidate_final.json'),'patch_sha256':report['patch_sha256']}))
if __name__=='__main__':main()
