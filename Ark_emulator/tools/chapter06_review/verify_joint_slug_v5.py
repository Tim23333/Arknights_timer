"""Reexecute true source death/splash/cold on the joint base with new CP bytes."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.chapter06.cold.policies import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    core=implementation_digest();assert core=='a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a'
    source=ROOT/'packages/campaign/chapter06_units/snslime/retained_v16/evidence'
    out=ROOT/'validation/campaign/chapter06_complete_base_v5/slug_probes';assert not out.exists();out.mkdir(parents=True)
    cold=ROOT/'packages/campaign/chapter06_cold/model.json';results=[]
    for case,expected in [('before_true_death',2),('before_expiry',2),('silenced',0),('discarded_member',1)]:
        inp=source/(case+'.probe.json');old=source/(case+'.replay.json');record=json.loads(old.read_bytes())
        assert all(c['submitted_at']==0 for c in record['commands'])
        reg=providers();program=Compiler(providers=reg).compile(inp,packages=[cold]);sim=Engine.create(program,seed=record['seed'],providers=reg)
        for cmd in sorted(record['commands'],key=lambda row:row['order']):sim.submit(cmd['action'],at=cmd['at'])
        until=33;sim.session.advance(1)
        cp=out/(case+'.checkpoint.json');pin=write_ordered(cp,sim.checkpoint());r=Engine.restore(program,load_bound(cp,pin),providers=reg)
        sim.session.advance(until-1);r.session.advance(until-1);head=replay(program,sim.export_replay(),providers=reg)
        assert sim.checkpoint()==r.checkpoint()==head.checkpoint()
        packets=[e for e in sim.session.events if e['type']=='damage.accepted' and e['payload']['source']==2]
        assert len(packets)==expected and all(e['time']==32 and e['payload']['amount']==500 for e in packets)
        assert not sim.ctx.alive(2) and sim.ctx.resources.current(2,'hp')==0
        cold_handles=[b for e in sim.session.world.entities() for b in e['components'].get('buffs',{}).get('instances',[]) if b['definition']=='buff/ch6/cold/e2c_cold']
        assert len(cold_handles)==expected and all(b['expires_at']==332 for b in cold_handles)
        assert not sim.ctx.projectiles._impact_payload_scopes and not sim.ctx.projectiles._area_payload_scopes
        results.append({'case':case,'passed':True,'actual500_packets':len(packets),'cold_handles':len(cold_handles),'cold_expiry':332,
                        'input_sha':sha(inp),'old_command_source_sha':sha(old),'new_checkpoint_sha':pin,'head_equal':True})
    assert implementation_digest()==core
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump({'passed':True,'core':core,'cases':results,'cold_module_sha':sha(cold),
        'scope':'Actual source death, 2 true AoE recipients and silence/withdraw controls on joint runtime; old CPs not used, no whole-stage approval'},f,indent=2)
    print(json.dumps({'passed':True,'cases':len(results),'sha':sha(target)}))


if __name__=='__main__':main()
