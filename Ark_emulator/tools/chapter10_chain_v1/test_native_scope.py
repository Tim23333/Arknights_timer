"""Actual sourced dkmage attack scope, including owned automatic cast cycle."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c10_chain_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from tools.chapter10_chain_v1.fixture import package
from tools.chapter10_chain_v1.native_module import mount
from tools.chapter10_chain_v1.test_author import proof,outcome,PROOFS


def main():
    data=package()
    provenance=mount(data,data['entities'][0])
    source=data['entities'][0]
    source['components']['attributes']['base'].update(provenance['source_attributes'])
    source['components']['resources']['hp'].update(initial=16000,capacity=16000)
    # All original probe ownership remains; its manual attack is never submitted.
    core=implementation_digest()
    sim=Engine.create(Compiler().compile(data),seed=17,event_journal_path=Path(os.environ['ARKSIM_RUN_DIR'])/'native.active.jsonl')
    sim=proof(sim,at=43,end=110)
    hits=outcome(sim,'projectile.hit')
    actual={
        'hits':[{k:e['payload'][k] for k in ('projectile','source','target','hit_count')}|{'time':e['time']} for e in hits],
        'hp':[sim.ctx.resources.current('target'+str(i),'hp') for i in range(5)],
        'EP':[sim.ctx.get('target'+str(i),('runtime','elemental','remaining','DARK')) for i in range(5)]}
    report={'schema':'ark-sim/native-chain-scope/v1','implementation':core,'provenance':provenance,
        'actual':actual,'actual_CP_head_proofs':PROOFS,'actual_game_accuracy_verified':False,
        'passed':len(hits)==4 and actual['hp']==[9450,9532.5,9602.625,9662.23125,10000] and implementation_digest()==core}
    out=ROOT/'validation/campaign/chapter10_chain_v1/native.scope.v1.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert report['passed'],actual
    sim.session.advance(140)
    launches=outcome(sim,'projectile.launched')
    report['actual_cycle_launches']=[e['time'] for e in launches]
    report['cycle_4seconds_actual']=len(launches)>=2 and launches[1]['time']-launches[0]['time']==120
    report['passed']=report['passed'] and report['cycle_4seconds_actual']
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    assert report['passed'],report['actual_cycle_launches']
    print(json.dumps({'passed':True,'core':core,'cycle':report['actual_cycle_launches']}))
    return 0
if __name__=='__main__':raise SystemExit(main())
