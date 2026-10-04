"""Persist actual sourceCold scaled frame casts through new content and v13."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT.parent/'unpack_work/campaign_retained_buff_payload_v13_candidate'
OUT=ROOT/'packages/campaign/chapter06_units/windup_v2_evidence'
CORE='a532397e5f2dbd405649ce2baaad6d79938de3256d52dc52e1da9d1f79ffcdbc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.domains.buff_application import pure_attributes
    from ark_sim.tools.replay import replay
    from tools.chapter06_units.test_windup_v2 import mage_singlecold,melee_singlecold
    from tools.chapter06_units.snmage.test_module_v13_v2 import deploy
    from tools.chapter06_units.test_melee_v13_v2 import deploy as melee_deploy
    from tools.chapter06_units.snmage.build_module import COLD
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    if implementation_digest()!=CORE:raise ValueError('Frozen v13 only')
    paths=[Path(__file__),ROOT/'tools/chapter06_units/build_windup_v2.py',ROOT/'tools/chapter06_units/test_windup_v2.py',ROOT/'packages/campaign/chapter06_units/melee_v2/model.json',ROOT/'packages/campaign/chapter06_units/snmage_v2/model.json',ROOT/'packages/campaign/chapter06_units/melee.model.json',ROOT/'packages/campaign/chapter06_units/snmage/model.json',COLD,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in paths};OUT.mkdir(parents=True,exist_ok=True);records=[]
    for name,initial,frame,native in [('mage_normal',0,29,None),('mage_skill',2,29,None),('shield',0,20,'enemy_1006_shield_2'),('snsbr',0,18,'enemy_1064_snsbr')]:
        mage=native is None;data=mage_singlecold(initial) if mage else melee_singlecold(native);path=OUT/(name+'.probe.json');write(path,data)
        reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6299,providers=reg)
        s.submit({'action':'skill','source':'controller','ability':'ability/ch6/cold/apply5'},at=0);(deploy if mage else melee_deploy)(s,at=1)
        s.session.advance(10);cp=OUT/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
        s.session.advance(30);restored.session.advance(30);rp=OUT/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
        owner=s.session.world.resolve('mage' if mage else 'enemy');began=next(e for e in s.session.events if e['type']=='ability.started' and e['payload']['source']==owner);event=next(e for e in s.session.events if e['type']==('projectile.launched' if mage else 'damage.accepted') and e['payload']['source']==owner)
        actual={'cast_started':began['time'],'payload_time':event['time'],'relative_native_clock':event['time']-began['time'],'source_attack_speed_ratio':pure_attributes(s.ctx,owner)['attack_speed_ratio'],'damage_packets':[(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']}
        obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
        if actual['relative_native_clock']!=frame or actual['source_attack_speed_ratio']!=.7 or obs!=cp_obs or obs!=rp_obs:raise ValueError('Actual public scaled clock/CP/head differs: '+name)
        records.append({'name':name,'actual':actual,'expected_relative_clock':frame,'end_tick':40,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':10,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(OUT/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Original/new/source/runtime guards changed')
    report={'schema':'ark-sim/ch6-windup-v2-author-evidence/v1','author_checks_passed':True,'core':CORE,'source_at_start':before,'source_at_completion':after,'old_bytes_preserved':True,'witnesses':records,'independent_reviewed':False,'formal_approved':False,'whole_stage_executed':False,'client_verified':False}
    p=OUT/'author.evidence.json';write(p,report);print(json.dumps({'author_checks_passed':True,'witnesses':4,'report_sha256':sha(p)}))
if __name__=='__main__':main()
