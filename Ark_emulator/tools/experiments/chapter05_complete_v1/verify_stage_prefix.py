"""Real compiled chapter5 prefixes; no substitution of the complete source plan."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.campaign_streaming_evidence import observations
from ark_sim.tools.replay import replay
PIN='8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert implementation_digest()==PIN
    out=ROOT/'validation/campaign/chapter05_complete_v1/prefix_v3';out.mkdir(parents=True,exist_ok=True);reports=[]
    for stage in ('09','10'):
        source=ROOT/('packages/campaign/chapter05_stage_models/combined_v3/level_main_05-'+stage+'.life99999.json')
        pin=sha(source);p=Compiler().compile(source);s=Engine.create(p)
        expected_count=4 if stage=='09' else 10
        actors=[e for e in s.session.world.entities() if e['definition_id']=='unit/ch5/ballista/source_level6']
        assert len(actors)==expected_count
        if stage=='10':assert all(not s.ctx.active(e['id']) and s.ctx.resources.current(e['id'],'sp')==0 for e in actors)
        else:assert all(s.ctx.active(e['id']) for e in actors)
        s.session.advance(150);cp=out/('05-'+stage+'.checkpoint.json')
        if cp.exists():raise FileExistsError('Preserve actual checkpoint')
        cp_pin=write_ordered(cp,s.checkpoint());r=Engine.restore(p,load_bound(cp,cp_pin))
        s.session.advance(150);r.session.advance(150)
        assert observations(s)==observations(r)==observations(replay(p,s.export_replay()))
        events=list(s.session.events);shots=sum(e['type']=='projectile.launched' for e in events)
        if stage=='09':assert shots>=4
        assert s.session.time==300 and s.ctx.state()['pending_waves']>0 and sha(source)==pin and implementation_digest()==PIN
        reports.append({'stage':'level_main_05-'+stage,'input_sha':pin,'program':p.fingerprint,'events':len(events),
            'projectiles':shots,'pending':s.ctx.state()['pending_waves'],'observations':observations(s),
            'checkpoint':str(cp),'checkpoint_sha':cp_pin,'checkpoint_replay_equal':True,'complete':False})
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump({'core':PIN,'exitcode':0,'stages':reports,'full_stage_executed':False},f,indent=2)
    print(json.dumps({'passed':True,'sha':sha(target),'stages':[{'id':r['stage'],'events':r['events']} for r in reports]}))
if __name__=='__main__':main()
