"""Execute converted native controls as an explicitly partial source scenario."""
from copy import deepcopy
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06_npcs.providers_v2 import providers
from tools.campaign_content_composition import compose_modules
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    inp=ROOT/'validation/campaign/chapter06_converter_v6_sources_strict/converted.json';data=json.loads(inp.read_bytes())
    files=[ROOT/'packages/campaign/chapter06_npcs'/n for n in ['swllow.v2.model.json','huang.v7.model.json','amiya.v3.model.json']]
    modules=[(p.name,json.loads(p.read_bytes())) for p in files]+[('exact_source_controls',{'definitions':data['controls']})]
    defs,_=compose_modules(modules);scene=deepcopy(data['scene']);omitted=[]
    for w in scene['timeline']['waves']:
        for f in w['fragments']:
            omitted += [a for a in f['actions'] if a['kind']=='spawn']
            f['actions']=[a for a in f['actions'] if a['kind']!='spawn']
    assert len(omitted)==1
    scene['id']='scene/ch6/v6_converted_controls_only';scene['objectives']={}
    scene['metadata']['explicit_subset']='Boss birth omitted. Actual source map and DP/0slots/story/activation preserved. No complete stage claim.'
    p={'schemaVersion':2,'definitions':list(defs.values()),'scenarioDraft':scene}
    out=ROOT/'validation/campaign/chapter06_converter_v6_control_runtime';out.mkdir(exist_ok=False)
    (out/'input.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),seed=scene['seed'],providers=reg)
    driver=PublicAckDriver(s);driver.advance_to(60)
    cp=out/'bundle.json';pin=write_ordered(cp,{'simulation':s.checkpoint(),'driver':driver.checkpoint()});loaded=load_bound(cp,pin)
    r=Engine.restore(s.program,loaded['simulation'],providers=reg);rd=PublicAckDriver(r,loaded['driver'])
    driver.advance_to(900);rd.advance_to(900);head=replay(s.program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint() and driver.checkpoint()==rd.checkpoint()
    times=[e['time'] for e in s.session.events if e['type']=='entity.activated'];assert times==[60,240,420]
    assert len(driver.submitted)==7 and sum(e['type']=='control.completed' for e in s.session.events)==5
    assert s.ctx.resources.current('system/battle','dp')==0 and scene['parameters']['deploy_capacity']==0
    report={'passed':True,'core':implementation_digest(),'activation_ticks':times,'public_ack_count':7,
        'source_pins':{str(p):sha(p) for p in [inp,*files,Path(__file__),ROOT/'tools/chapter06_review/stage_converter_v6.py',ROOT/'tools/chapter06_npcs/providers_v2.py']},
        'checkpoint_sha':pin,'head_and_restore_equal':True,'omitted_source_birth':omitted,
        'scope':'Actual strict v6 source-converted controls subset. Native map/options/seed preserved; pending Boss explicitly omitted. Not whole 6-17 or native callback timing proof.'}
    target=out/'verification.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
