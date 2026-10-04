"""No manual borrowing and no post-completion effects from a waiting cast."""
from copy import deepcopy
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_waiting_actions_v1_candidate'
sys.path.insert(0,str(RUNTIME));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.adapters.api import implementation_digest
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    data=json.loads((ROOT/'validation/campaign/waiting_actions_v1/bound/input.json').read_bytes())
    source_report=json.loads((ROOT/'packages/campaign/chapter07_boss/patrt/required_waiting_counters/report.json').read_bytes())
    cmds=source_report['results']['immo_waiting']['checkpoint']['commands']
    out=ROOT/'validation/campaign/waiting_actions_v1/bound_edges';out.mkdir(exist_ok=False);rows=[]
    def make(p):
        s=Engine.create(Compiler().compile(p),seed=7162)
        for c in cmds:s.submit(c['action'],at=c['at'])
        return s
    action=next(a['id'] for a in data['abilities'] if a['id'].endswith('/immo_action'))
    s=make(data);s.submit({'action':'skill','source':'boss','ability':action},at=10);s.advance(11)
    rejected=[e for e in s.session.events if e['type']=='command.rejected'];assert len(rejected)==1
    assert not any(e['type']=='ability.started' and e['payload']['ability']==action for e in s.session.events)
    assert s.checkpoint()==replay(s.program,s.export_replay()).checkpoint();rows.append({'manual_waiting_borrow_rejected':True})
    p=deepcopy(data);boss=next(d for d in p['entities'] if 'patrt' in d['id']);boss['components']['rebirth']['delay_seconds']=.3
    s=make(p);s.advance(16)
    assert s.ctx.active('boss') and not any(e['type']=='ability.started' and e['payload']['ability']==action for e in s.session.events)
    assert s.checkpoint()==replay(s.program,s.export_replay()).checkpoint();rows.append({'retained_timer_not_authorized_after_restore':True})
    p=deepcopy(data);boss=next(d for d in p['entities'] if 'patrt' in d['id']);boss['components']['rebirth']['delay_seconds']=1
    ability=next(a for a in p['abilities'] if a['id']==action);ability['timeline'][0]['at']=10
    s=make(p);s.advance(30);cp=out/'inflight30.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin))
    for sim in (s,r):sim.advance(15)
    assert s.ctx.active('boss') and not any(e['type']=='damage.accepted' and e['payload'].get('ability')==action for e in s.session.events)
    assert any(e['type']=='ability.interrupted' and e['payload']['reason']=='waiting_completed' for e in s.session.events)
    assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay()).checkpoint();rows.append({'inflight_waiting_effect_cancelled_at_finish':True,'checkpoint_sha':pin})
    target=out/'verification.json';target.write_text(json.dumps({'passed':True,'core':implementation_digest(),'cases':rows,
        'scope':'Finite actualwaiting action source lease; manual/afterrestore/inflight completion restrictions. Full typedsource target/foreignlease/failure/refresh bounds peer pending.'},indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'sha':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
