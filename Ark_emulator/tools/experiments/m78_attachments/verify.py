"""Actual-source M78 evidence with complete source/catalog/tool guards."""
from pathlib import Path
import contextlib,hashlib,importlib.util,io,json,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_m78_owned_attachment_candidate'
BASE=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
OUT=ROOT/'validation/campaign/m78_attachments'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as file:
        for block in iter(lambda:file.read(1048576),b''):h.update(block)
    return h.hexdigest()
def core(mapping):return hashlib.sha256(json.dumps(mapping,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def guard():
    roots={'source':(RUNTIME/'ark_sim','*.py'),'parent':(BASE/'ark_sim','*.py'),
        'catalog':(RUNTIME/'ark_sim','*.json'),'tools':(ROOT/'tools/candidates/m78_owned_attachments','*'),
        'experiments':(ROOT/'tools/experiments/m78_attachments','*.py')}
    result={name:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob(pattern))
        if p.is_file() and '__pycache__' not in p.parts} for name,(folder,pattern) in roots.items()}
    paths=[ROOT/'packages/campaign/chapter04_sources/native.reference.json',
        ROOT/'packages/campaign/chapter04_dmage/source.reference.json',
        ROOT/'packages/campaign/chapter04_dmage/module.reference.json',ROOT/'tools/audit_chapter04_dmage_sources.py',
        ROOT/'tools/build_chapter04_dmage_module.py',ROOT/'tools/campaign_ordered_checkpoint.py',
        ROOT/'packages/ark_content/level_main_00_01.json',ROOT/'packages/custom/custom_guard.json',
        ROOT/'scenarios/level_main_00_01/commands.json',ROOT.parent/'Ark_data/dump.cs',
        ROOT/'tools/experiments/m75_packet_order/test_packets.py',
        ROOT/'tools/experiments/m72_no_source_damage/test_no_source.py']
    result['consumed']={str(p):sha(p) for p in paths}
    return result

def main():
    import ark_sim,pytest
    assert Path(ark_sim.__file__).resolve().parent==RUNTIME/'ark_sim'
    before=guard();pin=implementation_digest()
    assert core(before['parent'])=='348c5671adfd73adb501c67a3dd4c51ce4f88228e45dcc6b1026c6eb2822bd57'
    for script in ['audit_chapter04_dmage_sources.py','build_chapter04_dmage_module.py']:
        subprocess.run([sys.executable,str(ROOT/'tools'/script),'--check'],cwd=ROOT,check=True,capture_output=True,text=True)
    cases=[]
    class Capture:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration,
                'longrepr':str(report.longrepr) if report.failed else None})
    selected=[str(Path(__file__).with_name('test_attachment.py')),
        'tools/experiments/m75_packet_order/test_packets.py','tools/experiments/m72_no_source_damage/test_no_source.py',
        'tests_v2/test_kernel.py','tests_v2/test_abilities.py','tests_v2/test_auras.py',
        'tests_v2/test_damage_hooks_random.py','tests_v2/test_event_resources.py','tests_v2/test_replay.py']
    code=int(pytest.main(selected+['-q','--tb=short'],plugins=[Capture()]))
    noopt=subprocess.run([sys.executable,str(Path(__file__).with_name('compare_parent.py'))],cwd=ROOT,capture_output=True,text=True)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'no-feature.log').write_text(noopt.stdout+noopt.stderr,encoding='utf8')
    assert noopt.returncode==0,noopt.stdout+noopt.stderr
    spec=importlib.util.spec_from_file_location('m78_builder',ROOT/'tools/candidates/m78_owned_attachments/build.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    with tempfile.TemporaryDirectory(prefix='m78_reproduce_',dir=RUNTIME.parent) as temporary:
        b.OUT=Path(temporary)/'candidate'
        with contextlib.redirect_stdout(io.StringIO()):b.main()
        assert b.core(b.OUT)==pin,'Fresh candidate source bytes differ'
    after=guard();assert before==after and implementation_digest()==pin,'Source/catalog/tools changed during run'
    module=next(m for name,m in sys.modules.items() if name.endswith('test_attachment'))
    modules={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.items()
        if (name=='ark_sim' or name.startswith('ark_sim.')) and getattr(m,'__file__',None)}
    assert all(Path(p).is_relative_to(RUNTIME/'ark_sim') for p in modules.values())
    report={'schema':'ark-sim/m78-owned-attachment-author-verification/v1','passed':code==0,
        'core_start':pin,'core_end':implementation_digest(),'parent_core':core(after['parent']),
        'start_manifest':before,'end_manifest':after,'guards_equal':True,'actual_modules':modules,
        'source_audit_sha256':sha(ROOT/'packages/campaign/chapter04_dmage/source.reference.json'),
        'source_module_sha256':sha(ROOT/'packages/campaign/chapter04_dmage/module.reference.json'),
        'builder_reproduction_source_bytes_equal':True,'cases':cases,'actual_inputs':module.INPUTS,
        'no_feature_comparison':'no_feature_comparison.json',
        'scope':['Actual dmage source26/30/20frames,trigger1,range3 versus normal2.5,175arts/s quantum integration',
            'Cast/link-owned infinite STUN refreshed1s and exact same-tick cleanup,explicitBUFF/SP policies',
            'Generic ownership/generation/RNG/goal rollback and completion blocking,actual orderedCP/replay',
            'Preserved M75 packet and M72 source-free boundaries plus selected baseline compatibility'],
        'limits':['Native Lasso/Link/MeleeModifierSplitter/Harpoon bodies and hatred comparator remain pending',
            'Victim ignoreForSp=False is a declared reference choice; node has no serialized switch',
            'Quantum left-endpoint integration is a reference policy,not native continuous packet calibration',
            'M84 immunity/M86-M88 rebirth/death/field composition not yet tested on this standalone branch',
            'No4-9 full49-spawn/36-stage/client-accuracy acceptance']}
    target=OUT/'verification.json'
    with target.open('x',encoding='utf8') as file:json.dump(report,file,ensure_ascii=False,indent=2);file.write('\n')
    print(json.dumps({'passed':report['passed'],'core':pin,'cases':len(cases),'failed':[c['case'] for c in cases if c['outcome']=='failed']}))
    assert code==0,'Actual compatibility or authored test failure'

if __name__=='__main__':main()
