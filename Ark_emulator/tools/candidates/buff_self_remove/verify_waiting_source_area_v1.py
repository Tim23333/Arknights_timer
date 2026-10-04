"""Waiting source remains unavailable as a target while its owned area executes."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_waiting_actions_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay


def main():
    p=json.loads((ROOT/'validation/campaign/waiting_actions_v1/ready/input.json').read_bytes())
    action=next(a for a in p['abilities'] if a['id'].endswith('/immo_action'))
    effect=action['timeline'][0]['effect'];action['timeline']=[{'at':0,'effect':{'op':'area','target':'source','center':'source','radius':1.75,'filters':[{'tag':'player'}],'effects':[effect]}}]
    cmds=json.loads((ROOT/'packages/campaign/chapter07_boss/patrt/required_waiting_counters/report.json').read_bytes())['results']['immo_waiting']['checkpoint']['commands']
    s=Engine.create(Compiler().compile(p),seed=7163)
    for c in cmds:s.submit(c['action'],at=c['at'])
    s.advance(31);areas=[e for e in s.session.events if e['type']=='area.resolved'];assert len(areas)==1 and areas[0]['time']==29
    damage=[e for e in s.session.events if e['type']=='damage.accepted' and e['payload'].get('ability')==action['id']];assert damage
    assert all(e['time']==29 and e['payload']['source']==s.session.world.resolve('boss') for e in damage)
    assert not s.ctx.active('boss') and s.ctx.alive('boss') and s.ctx.resources.current('boss','hp')==0
    assert s.checkpoint()==replay(s.program,s.export_replay()).checkpoint()
    out=ROOT/'validation/campaign/waiting_actions_v1/source_area';out.mkdir(exist_ok=False)
    (out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8');target=out/'verification.json'
    target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'actual_area_once_tick29':True,'actual_damage_packets':len(damage),'source_zero_inactive_waiting':True,'head_equal':True,'scope':'Generic source-centred waiting action dispatch only; source-specific typedtarget/quantity/customselectors separate.'},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
