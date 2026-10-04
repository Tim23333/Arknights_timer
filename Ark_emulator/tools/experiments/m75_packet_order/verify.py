"""Guarded M75 author evidence; frozen M73 failure and source reports preserved."""
from pathlib import Path
import contextlib,hashlib,importlib.util,io,json,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m73_environment_integrated_v2_candidate'
OUT=ROOT/'validation/campaign/m75_packets'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(mapping):return hashlib.sha256(json.dumps(mapping,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def guard():
    roots={'m75_source':(RUNTIME/'ark_sim','*.py'),'m73_source':(BASE/'ark_sim','*.py'),
           'm75_catalog':(RUNTIME/'ark_sim','*.json'),
           'builder_tools':(ROOT/'tools/candidates/m75_periodic_packets','*'),
           'experiments':(ROOT/'tools/experiments/m75_packet_order','*.py')}
    result={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern))
        if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
    paths=[ROOT/'packages/campaign/chapter04_environment/source.reference.json',
        ROOT/'packages/campaign/chapter04_environment/volcano.reference_module.json',
        ROOT/'packages/campaign/chapter04_plans/source.plan.json',ROOT/'tools/build_chapter04_volcano_module.py',
        ROOT/'tools/build_reference_stage_scenario_v2.py',ROOT/'tools/campaign_ordered_checkpoint.py',
        ROOT/'tools/experiments/m73_environment/test_volcano_source.py',
        ROOT/'tools/experiments/m73_environment_peer/test_peer.py',
        ROOT/'packages/ark_content/level_main_00_01.json',ROOT/'packages/custom/custom_guard.json',
        ROOT/'scenarios/level_main_00_01/commands.json']
    paths+=list((ROOT/'validation/campaign/m73_environment_peer/callback_reproduction').glob('*-fixture.json'))
    result['consumed_files']={str(p):sha(p) for p in paths}
    return result


def main():
    import ark_sim,pytest
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    before=guard();pin=implementation_digest()
    assert core(before['m73_source'])=='1b548c29fba3dd19c177fbb458a0226e496b15a03c5c2a3599243bcb20e40932'
    cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,
                'longrepr':str(report.longrepr) if report.failed else None})
    selection=[str(Path(__file__).with_name('test_packets.py')),
        'tools/experiments/m73_environment_peer/test_peer.py',
        'tools/experiments/m73_environment/test_volcano_source.py',
        'tests_v2/test_kernel.py','tests_v2/test_damage_hooks_random.py','tests_v2/test_event_resources.py',
        'tests_v2/test_scenario_effects.py','tests_v2/test_replay.py']
    code=int(pytest.main(selection+['-q','--tb=short'],plugins=[Capture()]))
    noopt=subprocess.run([sys.executable,str(Path(__file__).with_name('compare_parent.py'))],cwd=ROOT,capture_output=True,text=True)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'no-profile.log').write_text(noopt.stdout+noopt.stderr,encoding='utf8')
    assert noopt.returncode==0,noopt.stdout+noopt.stderr
    spec=importlib.util.spec_from_file_location('m75_build',ROOT/'tools/candidates/m75_periodic_packets/build.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='m75_reproduction_',dir=RUNTIME.parent) as tmp:
        builder.OUT=Path(tmp)/'candidate'
        with contextlib.redirect_stdout(io.StringIO()):builder.main()
        reproduced=builder.core(builder.OUT)
        assert reproduced==pin,'Fresh builder output differs from actual candidate'
    after=guard();assert before==after and implementation_digest()==pin
    modules={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.items()
        if (name=='ark_sim' or name.startswith('ark_sim.')) and getattr(module,'__file__',None)}
    assert all(Path(path).is_relative_to(RUNTIME/'ark_sim') for path in modules.values())
    report={'schema':'ark-sim/m75-periodic-packet-author-verification/v1','passed':code==0,
        'core':pin,'parent_core':core(after['m73_source']),'core_start':pin,'core_end':implementation_digest(),
        'start_manifest':before,'end_manifest':after,'guards_equal':True,'cases':cases,
        'actual_runtime_modules':modules,'builder_reproduction_core':reproduced,
        'no_profile_comparison':'no_profile_comparison.json',
        'scope':['World-owned same-frame FIFO packet continuation and owned scheduler identity',
            'Actual M73 authored retire/move failures fixed; legal ability.start/delay0 closure before next packet',
            'Per-packet and per-callback atomic boundaries, retained earlier packet and blocked failure checkpoint',
            'Synchronous field.triggered removal/finish/failure and duplicate scheduling/task ownership',
            'Actual eight native cell source probe through600 ticks, ordered CP/replay; not fullstage combat',
            'No-profile actual0-1 tick120/custom850 tick30 full values, types, float bits, raw phase compatibility'],
        'limits':['Numeric opt-in stage ordering is a declared model protocol, not native same-frame proof',
            'Already committed earlier packets are not rolled back across later scheduler callback failure',
            'Direct/manual pulse/packet handler invocation cannot consume scheduler-owned tasks',
            'No 4-9 complete battle,36-stage or client accuracy claim']}
    target=OUT/'verification.json'
    with target.open('x',encoding='utf8') as file:json.dump(report,file,ensure_ascii=False,indent=2);file.write('\n')
    print(json.dumps({'passed':report['passed'],'core':pin,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed']}))
    assert code==0,'Actual author or regression tests failed'

if __name__=='__main__':main()
