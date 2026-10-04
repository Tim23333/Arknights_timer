"""Execute actual native C6 draft prefix; no fullstage or final Boss claim."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06_review.build_stage_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source=ROOT/'validation/campaign/chapter06_join_draft_v1/06-14.json'
    p=json.loads(source.read_bytes());reg=providers();program=Compiler(providers=reg).compile(p)
    out=ROOT/'validation/campaign/chapter06_join_draft_prefix_v1';out.mkdir(exist_ok=False)
    s=Engine.create(program,seed=p['scenarioDraft']['seed'],providers=reg);s.advance(100)
    cp=out/'at100.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg)
    s.advance(120);r.advance(120);head=replay(program,s.export_replay(),providers=reg)
    assert s.checkpoint()==r.checkpoint()==head.checkpoint()
    registry=s.ctx.state()['predefined_registry'];assert set(registry)=={'trap_010_frosts#1','trap_010_frosts#2'}
    assert all(not s.ctx.active(ref) for ref in registry.values())
    report={'passed':True,'core':implementation_digest(),'package_sha':sha(source),'program':program.fingerprint,'runtime':s.runtime_fingerprint,
        'checkpoint_sha':pin,'head_and_restore_equal':True,'end_tick':220,'events':len(s.session.events),'predefined_dormant_count':2,
        'seed':p['scenarioDraft']['seed'],'native_life':s.ctx.resources.current('system/battle','life'),
        'scope':'Actual native draft6-16 full source join prefix, ordinaryBoss draft only. No whole-stage/sourceBoss final/nativeaccuracy acceptance.'}
    target=out/'verification.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':sha(target)}))


if __name__=='__main__':main()
