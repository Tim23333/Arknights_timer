from pathlib import Path
import hashlib,json,sys,subprocess
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m43_request_transform_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
OUT=ROOT/'validation/campaign/chapter02_fields_peer/m43';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    import pytest
    before=implementation_digest();assert before=='f58f3594fe12dbf35f070effba48984871469f4799f19d7004b24c0ab5bd6c11'
    fixtures=[];cases=[];original=Compiler.compile
    def capture(self,scenario,*args,**kwargs):
        p=OUT/f'input_{len(fixtures):02d}.json';p.write_text(json.dumps(thaw(scenario),ensure_ascii=False,indent=2)+'\n',encoding='utf8');fixtures.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
        return original(self,scenario,*args,**kwargs)
    class Results:
        def pytest_runtest_logreport(self,report):
            if report.when=='call':cases.append({'case':report.nodeid,'outcome':report.outcome,'seconds':report.duration})
    Compiler.compile=capture;code=pytest.main([str(ROOT/'tools/experiments/chapter02_fields_peer/test_m43_fields.py'),'-q'],plugins=[Results()]);Compiler.compile=original
    assert code==0
    from tools.experiments.chapter02_fields_peer.test_m43_fields import fixture,load
    actual=[]
    for name in ('weedy','custom'):
        p=fixture()
        if name=='weedy':
            row=next(x for x in load('skills.weedy.json')['rules'] if x['id']=='rule/campaign_weedy_distance_damage');p['rules'].append(row)
            effect={'op':'damage','damage_type':'true','distance':.5,'parameters':{'value':1200,'per_distance':1},'rules':{'damage.pipeline':row['id']}};expected=4400
        else:
            p['rules'].append({'id':'rule/custom','kind':'rule','contract':'damage.pipeline','implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':inputs.effect.amount+inputs.effect.parameters.vector[1],'allocations':[],'events':[]}"}],'output':'nodes.result'}})
            effect={'op':'damage','damage_type':'true','amount':25,'parameters':{'vector':[11,3],'damage_hook_locks':['buff/unrelated']},'metadata':{'retained':True},'rules':{'damage.pipeline':'rule/custom'}};expected=4972
        p['abilities'][0]['activation']['on_start'][0]=effect;program=Compiler().compile(p);s=Engine.create(program,seed=4243)
        commands=[{'action':'skill','source':'caster','ability':'ability/hit','at':3}];s.submit({k:v for k,v in commands[0].items() if k!='at'},at=3);s.advance(2)
        directory=OUT/name;directory.mkdir(exist_ok=True);cp=directory/'checkpoint.ordered.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h));s.advance(4);r.advance(4)
        assert s.ctx.resources.current('enemy','hp')==expected and s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()
        for file,value in [('input.json',p),('commands.json',commands),('replay.json',s.export_replay()),('final.json',s.snapshot())]:
            (directory/file).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        actual.append({'case':name,'expected_HP':expected,'actual_HP':s.ctx.resources.current('enemy','hp'),'checkpoint_resume_equal':True,'command_replay_equal':True,'files':{str(path.relative_to(ROOT)):sha(path) for path in directory.iterdir()}})
    result=subprocess.run([sys.executable,'tools/build_chapter02_tile_request_models.py','--check'],cwd=ROOT,text=True,capture_output=True,encoding='utf8');assert result.returncode==0
    (OUT/'builder_check.log').write_text(result.stdout+result.stderr,encoding='utf8')
    after=implementation_digest();assert before==after
    locks=['tools/build_chapter02_tile_request_models.py','packages/campaign/chapter02_tiles/buffs.lossless_request.model.json','packages/campaign/chapter02_tiles/fields.lossless_request.model.json','packages/campaign/skills.weedy.json','tools/experiments/chapter02_fields_peer/test_m43_fields.py',str(Path(__file__).relative_to(ROOT))]
    old=ROOT/'validation/campaign/chapter02_fields_peer/weedy_distance_original_failure.json'
    report={'schema':'ark-sim/independent-content-review/v1','status':'passed_declared_math_profile','core_before':before,'core_after':after,'actual_module':sys.modules['ark_sim'].__file__,
        'cases':cases,'actual_fixtures':fixtures,'source_locks':{x:sha(ROOT/x) for x in locks},'public_evidence':actual,
        'original_failure':{'path':str(old.relative_to(ROOT)),'sha256':sha(old)},'actual_client_verified':False,'formal_approved':False,
        'scope':'Lossless typed request transform and reference-field composition; actual Weedy selected pure pipeline 600, independent preDEF and resistance calculations; source native true damage application still pending feedback.'}
    (OUT/'final_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':len(cases),'core':before,'report_sha256':sha(OUT/'final_review.json')}))
if __name__=='__main__':main()
