"""Actual source inputs rerun on the new joint core; old receipts stay old."""
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
    out=ROOT/'validation/campaign/chapter06_complete_base_v5/source_probes';assert not out.exists();out.mkdir(parents=True)
    cold=ROOT/'packages/campaign/chapter06_cold/model.json';results=[]
    for case,frame in [('shield',20),('snsbr',18),('mage_normal',29),('mage_skill',29)]:
        inp=ROOT/('packages/campaign/chapter06_units/windup_v2_evidence/'+case+'.probe.json')
        old_record=ROOT/('packages/campaign/chapter06_units/windup_v2_evidence/'+case+'.replay.json')
        record=json.loads(old_record.read_bytes());assert all(c['submitted_at']==0 for c in record['commands'])
        registry=providers();program=Compiler(providers=registry).compile(inp,packages=[cold]);sim=Engine.create(program,seed=record['seed'],providers=registry)
        for cmd in sorted(record['commands'],key=lambda row:row['order']):sim.submit(cmd['action'],at=cmd['at'])
        sim.session.advance(3);cp=out/(case+'.checkpoint.json');pin=write_ordered(cp,sim.checkpoint());continued=Engine.restore(program,load_bound(cp,pin),providers=registry)
        sim.session.advance(record['until']-3);continued.session.advance(record['until']-3)
        head=replay(program,sim.export_replay(),providers=registry)
        assert sim.checkpoint()==continued.checkpoint()==head.checkpoint()
        started=[e for e in sim.session.events if e['type']=='ability.started' and e['payload']['source']==2]
        packets=[e for e in sim.session.events if e['type']==('projectile.launched' if case.startswith('mage') else 'damage.accepted') and e['payload']['source']==2]
        assert started and packets
        observed=packets[0]['time']-started[0]['time'];assert observed==frame,(case,observed,frame)
        results.append({'case':case,'passed':True,'relative_payload_frame':observed,'checkpoint_sha':pin,'input_sha':sha(inp),
                        'command_source_sha':sha(old_record),'actual_new_record':sim.export_replay(),'event_count':len(sim.session.events)})
    assert implementation_digest()==core
    target=out/'verification.json'
    with target.open('x',encoding='utf8') as f:json.dump({'core':core,'passed':True,'results':results,'cold_module_sha':sha(cold),
        'helper_sha':sha(Path(__file__)),'scope':'Fresh actual source inputs/public commands on joint core, independent constant windup expectations, no old CP migration/whole-stage approval'},f,indent=2)
    print(json.dumps({'passed':True,'cases':len(results),'sha':sha(target)}))


if __name__=='__main__':main()
