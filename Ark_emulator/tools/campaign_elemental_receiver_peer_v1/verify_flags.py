"""Live buff immunity projection and enemy-side rejection, independent public gates."""
import copy,json,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.campaign_elemental_receiver_peer_v1 import verify as v
from tools.campaign_elemental_receivers_v1.build import module
def main():
    rows=[]
    try:
        d,t,src,_=v.package()
        d['definitions'].extend([{'id':'buff/peer/element_free','kind':'buff','duration_seconds':10,'selection_flags':{'abnormal_flags':[21]}},
          {'id':'buff/peer/immune','kind':'buff','duration_seconds':1,'selection_flags':{'abnormal_immunes':[21]}}])
        v.effect(d,src,{'op':'apply_buff','target':2,'buff':'buff/peer/element_free'},3)
        v.effect(d,src,{'op':'apply_buff','target':2,'buff':'buff/peer/immune'},4)
        v.packet(d,src,'DARK',113,9);v.packet(d,src,'DARK',113,40)
        v.effect(d,src,{'op':'remove_buff','target':2,'buff':'buff/peer/element_free'},45);v.packet(d,src,'DARK',113,50)
        s=v.cpp(v.make(v.finish(d,t),'live_flag_projection'),40,53,'live_flag_projection')
        assert v.state(s)['remaining']['DARK']==774
        losses=v.events(s,'elemental.loss.accepted');assert [e['time'] for e in losses]==[9,50]
        rows.append({'case':'live_buff_flag_immune_expiry_removal_projection','passed':True,'loss_ticks':[e['time'] for e in losses]})
    except Exception:rows.append({'case':'live_buff_flag_immune_expiry_removal_projection','passed':False,'error':traceback.format_exc()})
    try:
        d,t,src,_=v.package();t['components']['selection_state']['side']=1
        data=module();t['components']['elemental']=copy.deepcopy(data['receiver_template']);d['definitions'].extend(data['rules']+data['buffs'])
        v.packet(d,src,'DARK',113,9);s=v.cpp(v.make(d,'enemy_side'),10,15,'enemy_side');assert v.state(s)['remaining']['DARK']==1000
        rows.append({'case':'explicit_enemy_receiver_declared_but_ally_profile_rejects','passed':True})
    except Exception:rows.append({'case':'explicit_enemy_receiver_declared_but_ally_profile_rejects','passed':False,'error':traceback.format_exc()})
    result={'schema':'ark-sim/elemental-receiver-peer-live-flags/v1','cases':rows,'actual_CP_head_proofs':v.PROOFS,'passed':all(r['passed'] for r in rows),'peer_sha256':v.sha(__file__)}
    v.OUT.with_name('flags.v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(rows),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
