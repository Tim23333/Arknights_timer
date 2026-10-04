from pathlib import Path
import hashlib,json,sys,subprocess
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate';sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter02_twelve_peer/combat_guard';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,v):path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    import pytest
    before=implementation_digest();assert before=='a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9'
    cases=[];inputs=[];original=Compiler.compile
    def capture(self,p,*args,**kwargs):
        path=OUT/f'input_{len(inputs):02d}.json';write(path,thaw(p));inputs.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path)});return original(self,p,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=capture;code=pytest.main([str(Path(__file__).with_name('test_guard.py')),str(Path(__file__).with_name('test_guard_source.py')),'-q'],plugins=[Results()]);Compiler.compile=original;assert code==0
    from tools.experiments.chapter02_twelve_peer.test_guard import block_scene
    public=[]
    for name in ('enemy_1011_wizard','enemy_1028_mocock','enemy_1018_aoemag'):
        p=block_scene(name);program=Compiler().compile(p);s=Engine.create(program,seed=4824);commands=[{'action':'deploy','entity':'unit/peer/blocker','position':{'row':2,'col':2},'alias':'blocker','at':0}]
        s.submit({k:v for k,v in commands[0].items() if k!='at'},at=0);s.advance(2);directory=OUT/name;directory.mkdir(exist_ok=True);path=directory/'checkpoint.ordered.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(38);r.advance(38)
        assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
        areas=[thaw(e) for e in s.session.events if e['type']=='area.resolved'];packets=[thaw(e) for e in s.session.events if e['type']=='damage.accepted']
        if name=='enemy_1018_aoemag':assert areas[0]['payload']['target']==s.session.world.resolve('blocker')
        else:assert all(e['payload']['target']==s.session.world.resolve('blocker') for e in packets)
        for filename,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:write(directory/filename,value)
        public.append({'native_enemy_id':name,'actual_blocker':s.ctx.spatial.blocked_by('enemy'),'observed_packets':packets,'observed_areas':areas,
            'checkpoint_resume_equal':True,'command_replay_equal':True,'files':{str(p.relative_to(ROOT)):sha(p) for p in directory.iterdir()}})
    check=subprocess.run([sys.executable,'-c',"import sys,runpy; sys.path.insert(0,"+repr(str(RUNTIME))+"); sys.argv=['build_chapter02_10_combat_guard','--check']; runpy.run_module('tools.build_chapter02_10_combat_guard',run_name='__main__')"],cwd=ROOT,capture_output=True,text=True,encoding='utf8');assert check.returncode==0,check.stderr
    (OUT/'builder_check.log').write_text(check.stdout+check.stderr,encoding='utf8')
    after=implementation_digest();assert before==after
    names=['packages/campaign/chapter02_units/main_02-10.enemies.combat_guard.reference_module.json','packages/campaign/chapter02_units/main_02-10.enemies.reference_module.json',
        'packages/campaign/chapter02_sources/native.reference.json','packages/campaign/native_reference/level_main_02-10.json','tools/build_chapter02_10_combat_guard.py',
        'tools/experiments/chapter02_twelve_peer/test_guard.py','tools/experiments/chapter02_twelve_peer/test_guard_source.py',str(Path(__file__).relative_to(ROOT))]
    old=ROOT/'validation/campaign/chapter02_twelve_peer/taunt_failure/original_failure.json'
    report={'schema':'ark-sim/independent-twelve-module-review/v1','status':'passed_declared_reference_profile','core_before':before,'core_after':after,'actual_module':sys.modules['ark_sim'].__file__,
        'cases':cases,'actual_compile_inputs':inputs,'public_evidence':public,'source_locks':{x:sha(ROOT/x) for x in names},'old_counterexample':{'path':str(old.relative_to(ROOT)),'sha256':sha(old)},
        'scope':['all12 source DB refs/overrides/motion/attrs','actual12 life losses versus leak entity count','fresh Unity INPUT_TARGET2 combat nodes','blocked candidate qualification, no arbitrary-taunt fallback','AOEmag21 and cross5 including flying splash, actual2.2 boundary policy','mob variants independent attack-frame/damage','owned definitions and selected abilities unchanged outside three binding guard','same-core ordered disk CP/command replay'],
        'actual_client_verified':False,'formal_approved':False,'whole_stage_executed':False}
    write(OUT/'final_review.json',report);print(json.dumps({'passed':len(cases),'core':before,'report_sha256':sha(OUT/'final_review.json')}))
if __name__=='__main__':main()
