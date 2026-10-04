"""Actual multi-packet source skill checks one accepted low-HP recovery."""
from copy import deepcopy
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_buff_self_remove_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.chapter06_npcs.huang_v6_policy import providers
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def main():
    p=json.loads((ROOT/'validation/campaign/chapter06_npc_huang_v7_guarded/0/input.json').read_bytes())
    ability=next(a for a in p['abilities'] if a['id']=='ability/peer/hit')
    ability['activation']['on_start']*=2
    out=ROOT/'validation/campaign/chapter06_npc_huang_v7_sameframe';out.mkdir(exist_ok=False)
    (out/'input.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf8')
    reg=providers();s=Engine.create(Compiler(providers=reg).compile(p),providers=reg,seed=6471)
    s.submit({'action':'skill','source':'dealer','ability':'ability/peer/hit'},at=10)
    s.submit({'action':'skill','source':'dealer','ability':'ability/peer/hit'},at=191)
    s.advance(9);cp=out/'before_damage.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin),providers=reg)
    for sim in (s,r):sim.advance(3)
    positive=[e for e in s.session.events if e['type']=='resource.changed' and e['payload'].get('target')==2 and e['payload'].get('resource')=='hp' and e['payload'].get('delta',0)>0]
    assert len(positive)==1 and positive[0]['payload']['delta']==1152.5
    assert s.ctx.resources.current('native_npc','hp')==1153.5
    for sim in (s,r):sim.advance(181)
    assert not s.ctx.active('native_npc')
    head=replay(s.program,s.export_replay(),providers=reg);assert s.checkpoint()==r.checkpoint()==head.checkpoint()
    report={'passed':True,'one_heal_after_two_sameframe_packets':True,'heal':1152.5,'post_damage_hp':1153.5,
        'normal_death_after_6s':True,'checkpoint_sha':pin,'head_and_restore_equal':True,
        'policy_sha':hashlib.sha256((ROOT/'tools/chapter06_npcs/huang_v6_policy.py').read_bytes()).hexdigest(),
        'events':thaw(tuple(s.session.events)),'scope':'Deferred source reaction policy; actual native synchronous callback ordering remains pending'}
    path=out/'verification.json';path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'sha':hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
