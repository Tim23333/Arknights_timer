"""Resume diagnostic: compare every stored field before failed owned task."""
import sys,os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CAND=(ROOT/'../unpack_work/campaign_c10_bloodline_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from tools.chapter10_bloodline_v1.test_author import fixture,providers,Engine,Compiler,cp
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
OUT=ROOT/'validation/campaign/chapter10_bloodline_v1'
def main():
    p=fixture('enemy_1222_dpvt',True);p['scenarioDraft']['commands']=[{'at':7,'action':'skill','source':'player','ability':'ability/blood/test/kill'}]
    def fail(inputs,params,context):raise ValueError('source placement late fault after real RNG')
    reg=providers();reg['fault/placement']={'callable':fail,'version':'1'}
    next(r for r in p['rules'] if r['id']=='rule/ch10/bloodline/placement')['implementation']['provider']='fault/placement'
    s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=1220);s.advance(37)
    calls=[];sample=s.session.random.sample
    def observed(stream):calls.append(stream);return sample(stream)
    s.session.random.sample=observed;captured=[]
    def stores():return {'world':s.session.world.snapshot(),'scheduler':s.session.scheduler.snapshot(),'events':s.session._events.snapshot(),'random':s.session.random.snapshot(),'attribute_cache':s.ctx.attributes.checkpoint_cache()}
    def capture_task():
        task=s.session.current_task
        if s.session._atomic_depth==0 and task is not None and task['kind']=='domain.death_spawn':captured.append({'stores':stores(),'time':s.session.time,'task':thaw(task),'active_key':s.session._active_key,'failure':s.session._failure})
        return None
    s.session.register_atomic_participant('test.failing_task_observation',capture_task,lambda value:None)
    error=None
    try:s.advance(1)
    except (ValueError,RuntimeError) as e:error={'type':type(e).__name__,'message':str(e)}
    after=stores();differences=[]
    def walk(a,b,path):
        if isinstance(a,dict) and isinstance(b,dict):
            for key in sorted(set(a)|set(b)):
                if key not in a or key not in b:differences.append({'path':path+'.'+str(key),'before':a.get(key),'after':b.get(key)})
                else:walk(a[key],b[key],path+'.'+str(key))
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):differences.append({'path':path+'.length','before':len(a),'after':len(b)})
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'['+str(i)+']')
        elif a!=b:differences.append({'path':path,'before':a,'after':b})
    if captured:walk(captured[0]['stores'],after,'stores')
    receipt={'core':implementation_digest(),'capture_count':len(captured),'capture_clock':[c['time'] for c in captured],'captured_task':[c['task'] for c in captured],
             'after_clock':s.session.time,'failure':s.session._failure,'observed_draw_calls':calls,'error':error,'store_equal':bool(captured) and captured[0]['stores']==after,'differences':differences[:30],'difference_count':len(differences),
             'all_store_keys_compared':['world','scheduler','events','random','attribute_cache'],'no_comparison_fields_removed':True}
    path=OUT/'latefault.resume.diff.v3.json';assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'capture_count':len(captured),'difference_count':len(differences),'error':error}));return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        import traceback
        p=OUT/'latefault.probe.serialization.failure.v3.json';p.write_text(json.dumps({'error':str(error),'traceback':traceback.format_exc()},indent=2),encoding='utf8');raise
