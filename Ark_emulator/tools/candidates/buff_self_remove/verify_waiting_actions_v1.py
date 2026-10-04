"""Actual source waiting action request uses a finite owned lifecycle lease."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_waiting_actions_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    folder=ROOT/'packages/campaign/chapter07_boss/patrt/required_waiting_counters'
    p=json.loads((folder/'immo_waiting.input.json').read_bytes());raw=json.loads((folder/'report.json').read_bytes())['results']['immo_waiting']['checkpoint']['commands']
    unit=next(d for d in p['entities'] if 'patrt' in d['id']);action=next(a['id'] for a in p['abilities'] if a['id'].endswith('/immo_action'))
    buff=next(b['id'] for b in p['buffs'] if any(e.get('op')=='trigger_ability' for e in b.get('effects',[])))
    unit['components']['rebirth']['retain_buffs'].append(buff)
    unit['components']['rebirth']['waiting_actions']={'abilities':[action],'buffs':[buff]}
    out=ROOT/'validation/campaign/waiting_actions_v1';out.mkdir(exist_ok=False);(out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8')
    s=Engine.create(Compiler().compile(p),seed=7161)
    for c in raw:s.submit(c['action'],at=c['at'])
    s.advance(6);assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
    cp=out/'waiting6.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    s.advance(25);r.advance(25);head=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()==head.checkpoint()
    starts=[e for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==action]
    assert len(starts)==1 and starts[0]['time']==29,starts
    assert s.ctx.resources.current('boss','hp')==0 and not s.ctx.active('boss') and s.ctx.alive('boss')
    report={'passed':True,'core':implementation_digest(),'actual_start_tick':29,'source_still_zero_hp_inactive_waiting':True,
        'checkpoint_sha':pin,'head_and_restore_equal':True,'scope':'First actual retained source timer action during waiting, no HPgrant/active rewrite. Full typedtarget/area source and generation/callback negative gates pending.'}
    p=out/'verification.json';p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'core':implementation_digest(),'sha':hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
