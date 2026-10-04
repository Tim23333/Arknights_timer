"""Real DP/SP admission of the fixed12 candidate opening with ordered recovery."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter06_review.runner_providers_v1 import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    package=ROOT/'validation/campaign/chapter06_join_draft_v2/06-14.life99999.json'
    commands=ROOT/'scenarios/campaign/chapter06/level_main_06-14/public_plan_v2/commands.json'
    p=json.loads(package.read_bytes());cmds=json.loads(commands.read_bytes());reg=providers()
    s=Engine.create(Compiler(providers=reg).compile(p),seed=p['scenarioDraft']['seed'],providers=reg)
    out=ROOT/'validation/campaign/chapter06_public_prefix_v2';out.mkdir(exist_ok=False)
    for c in cmds:
        a=dict(c);tick=a.pop('at');s.submit(a,at=tick)
    s.advance(200);cp=out/'at200.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
    for sim in (s,r):sim.advance(730)
    head=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==head.checkpoint()
    actual=[e for e in s.session.events if e['type'] in ('command.accepted','command.rejected')]
    (out/'commands.actual.json').write_text(json.dumps(thaw(tuple(actual)),indent=2)+'\n',encoding='utf8')
    report={'passed':True,'package_sha':sha(package),'commands_sha':sha(commands),'checkpoint_sha':pin,
        'end_tick':930,'events':len(s.session.events),'actual':thaw(tuple(actual)),'head_and_restore_equal':True,
        'dp':s.ctx.resources.current('system/battle','dp'),'scope':'Real candidate source opening admission only. Later12 deployment/whole-stage and finalizedBoss scope unverified.'}
    path=out/'verification.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'sha':sha(path),'results':thaw(tuple(actual))}))


if __name__=='__main__':main()
