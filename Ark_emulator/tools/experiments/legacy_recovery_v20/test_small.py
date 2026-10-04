"""Check the actual old-core public segmented continuation and replay path."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m52_visibility_stock_integrated_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations
from tools.finish_pending_runthrough_v17 import segmented_replay


def main():
    pin='bfbd9613dc36f2ac39c91381f57e8e4f7d306386514843d8b83ea020e45580fe';assert implementation_digest()==pin
    package=ROOT/'packages/campaign/runthrough/level_main_02-09.m52.yokai2_move.life99999.json'
    p=Compiler().compile(package);s=Engine.create(p,seed=875354927)
    commands=json.loads((ROOT/'scenarios/campaign/chapter02/02-09/commands.runthrough_exploratory_v1.json').read_bytes())
    for command in commands:
        if command['at']>=20:continue
        action=dict(command);tick=action.pop('at');s.submit(action,at=tick)
    s.session.advance(10);out=ROOT/'validation/campaign/legacy_recovery_v20';out.mkdir(parents=True,exist_ok=True)
    cp=out/'small.checkpoint.json'
    if cp.exists():raise FileExistsError('Preserve small proof')
    digest=write_ordered(cp,s.checkpoint());r=Engine.restore(p,load_bound(cp,digest))
    s.session.advance(10);r.session.advance(10);actual=observations(s);continued=observations(r)
    replayed=segmented_replay(p,s.export_replay(),3);repeated=observations(replayed)
    assert actual==continued==repeated and implementation_digest()==pin
    target=out/'small.json'
    with target.open('x',encoding='utf8') as f:json.dump({'core':pin,'program':p.fingerprint,'checkpoint_sha':digest,
        'actual':actual,'continued':continued,'replayed':repeated,'passed':True,'whole_stage_executed':False},f,indent=2)
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
