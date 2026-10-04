"""Consume source restartFSM through explicit finite generic operation."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];CAND=ROOT.parent/'unpack_work/campaign_behavior_restart_v1_candidate';sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
from tools.chapter08_boss.talula_skill_policies_v2 import providers
CORE='072aa9df680fef0760311b363a0cbccf105bea2bf3a5af563ddd3c9d1ca02d86'
OUT=ROOT/'packages/campaign/chapter08_consumers/boss/talula.restart.v1.reference.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
    assert implementation_digest()==CORE
    parent=ROOT/'packages/campaign/chapter08_consumers/boss/talula.skills.v2.reference.json';assert sha(parent)=='8fb847df71747c4cbabc01820fac886cd821ddbc77c635820d4a2d81aa9b1290'
    p=json.loads(parent.read_bytes());unit=p['entities'][0]['components'];behavior=p['behaviors'][0];old=behavior['transitions'][0];effects=deepcopy(old['effects']);behavior['states']['half']['on_enter']=effects
    clocks={a['id']:a['initial_cooldown_seconds'] for a in p['abilities'] if a['activation']['mode']=='manual' and '/1/' in a['id']}
    assert set(clocks.values())=={7,15}
    old['to']='half';old['effects']=[]
    # The HP transition enters a gate state, whose one explicit effect restarts
    # into half. This avoids double on_enter and puts all cancellation/clock
    # mutation into the same restart transaction.
    old['to']='half_restart'
    behavior['states']['half_restart']={'on_enter':[{'op':'restart_behavior','target':'self','state':'half','parameters':{
        'abilities':list(unit['abilities']),'reset_attack_clock':True,'initial_cooldowns':clocks,'reason':'source_switch_mode_restart_fsm'}}]}
    meta=p['manifest']['metadata'];meta['source_locks'].update({parent.relative_to(ROOT).as_posix():sha(parent),Path(__file__).relative_to(ROOT).as_posix():sha(Path(__file__))});meta['required_runtime']=CORE
    meta['reference_policy']['restart_FSM']='Source restartTrue: finite allactorabilities cancel pending ownedcasts, retain alreadylaunched projectile strategy, reset attackclock and mode1 initial7/15 relative to actual threshold boundary. Fullsource dispatch details remain declared reference.'
    meta['partial_consumer_scope']='Two modes attacks/four skills/rage/burn and explicitFSMrestart consumed; statusresistance and fullstage/source accuracy audit pending.'
    meta['pending_required_consumers']=['Statusresistance exact parentduration rules','Original fullstage integration/native control/environment consumers and independent admission']
    p['manifest']['id']='package/ch8/talula/restart_v1'
    f=deepcopy(p);f['scenarioDraft']={'id':'scene/talula/restart_compile','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':4},'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':0,'col':0}}]};Compiler(providers=providers()).compile(f);return p
if __name__=='__main__':
    p=build();assert not OUT.exists();OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'sha':sha(OUT),'actual_compile':True}))
