"""Persist real source-death AoE, source-silence and actual-member discard CP/head."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
RUNTIME=ROOT.parent/'unpack_work/campaign_retained_area_payload_v16_candidate'
DEST=ROOT/'packages/campaign/chapter06_units/snslime/retained_v16/evidence'
CORE='8b9f226882502ce9b9d8029102fff5832f2ba01e5449096502908b670d889e9b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def main():
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(RUNTIME))
    from ark_sim import Compiler,Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.tools.replay import replay
    from ark_sim.domains.buff_application import pure_attributes
    from tools.chapter06_units.snslime.test_required_payload import package,public_inputs,COLD
    from tools.chapter06_units.snslime.test_module_v16 import silenced_package,hp,flags,outgoing
    from tools.chapter06_units.snslime.build_module import OUT
    from tools.chapter06.cold.policies import providers
    from tools.campaign_ordered_checkpoint import write_ordered,load_bound
    from tools.campaign_streaming_evidence import observations,export_events
    base=DEST.parent;tests=base/'author.tests.json';result=json.loads(tests.read_bytes())
    if implementation_digest()!=CORE or not result['passed'] or result['implementation_after']!=CORE:raise ValueError('Actual frozen16 author tests required')
    paths=[Path(__file__),ROOT/'tools/chapter06_units/snslime/build_module.py',ROOT/'tools/chapter06_units/snslime/test_required_payload.py',ROOT/'tools/chapter06_units/snslime/test_module_v16.py',OUT,OUT.parent/'required.death_aoe.actual.json',OUT.parent/'required.death_aoe.tests.json',tests,COLD,ROOT/'tools/chapter06/cold/policies.py',RUNTIME/'ark_sim/rules/contracts.json']
    before={str(p):sha(p) for p in paths};DEST.mkdir(parents=True,exist_ok=True);records=[]
    for name,tick,hps in [('before_true_death',1,(9500,9500)),('before_expiry',31,(9500,9500)),('silenced',1,(10000,10000)),('discarded_member',3,(9500,10000)),('flying_member',1,(9500,10000))]:
        p=silenced_package() if name=='silenced' else package()
        if name=='flying_member':p['entities'][2]['components']['selection_state']['motion']=2
        path=DEST/(name+'.probe.json');write(path,p);reg=providers();program=Compiler(providers=reg).compile(path,packages=[COLD]);s=Engine.create(program,seed=6267,providers=reg);public_inputs(s)
        if name=='silenced':s.submit({'action':'skill','source':'killer','ability':'ability/test/snslime/silence'},at=1)
        if name=='discarded_member':s.submit({'action':'withdraw','source':'friend'},at=10)
        s.session.advance(tick);cp=DEST/(name+'.checkpoint.json');pin=write_ordered(cp,s.checkpoint());restored=Engine.restore(program,load_bound(cp,pin),providers=reg)
        s.session.advance(33-tick);restored.session.advance(33-tick)
        middle={'time':33,'source_alive':s.ctx.alive('slime'),'source_hp':hp(s,'slime'),'targets':{who:{'hp':hp(s,who),'flags':flags(s,who),'buffs':s.ctx.get(who,('buffs','instances'),[]),'attack_speed_ratio':pure_attributes(s.ctx,s.session.world.resolve(who))['attack_speed_ratio']} for who in ('killer','friend')},'outgoing':outgoing(s)}
        if middle['source_alive'] or middle['source_hp']!=0 or (hp(s,'killer'),hp(s,'friend'))!=hps:raise ValueError('Actual source death/accepted area packet differs: '+name)
        for who,expected_hp in zip(('killer','friend'),hps):
            if (23 in flags(s,who))!=(expected_hp==9500):raise ValueError('Actual accepted member Cold differs')
            if expected_hp==9500 and (len(middle['targets'][who]['buffs'])!=1 or middle['targets'][who]['buffs'][0]['expires_at']!=332):raise ValueError('Exact Cold10 expiry332 required')
        s.session.advance(301);restored.session.advance(301);rp=DEST/(name+'.replay.json');write(rp,s.export_replay());repeated=replay(program,json.loads(rp.read_bytes()),providers=reg)
        obs=observations(s);cp_obs=observations(restored);rp_obs=observations(repeated)
        if obs!=cp_obs or obs!=rp_obs or flags(s,'killer') or flags(s,'friend') or hp(s,'slime')!=0:raise ValueError('Actual durable/head/source/expiry differs')
        records.append({'name':name,'actual_middle':middle,'end_tick':334,'program':program.fingerprint,'runtime':s.runtime_fingerprint,'package':{'path':str(path),'sha256':sha(path)},'checkpoint':{'path':str(cp),'sha256':pin,'tick':tick,'actually_reloaded':True},'replay':{'path':str(rp),'sha256':sha(rp)},'journal':export_events(DEST/(name+'.events.jsonl'),s),'observations':obs,'checkpoint_observations':cp_obs,'replay_observations':rp_obs,'checkpoint_equal':True,'replay_equal':True})
    after={str(p):sha(p) for p in paths}
    if before!=after or implementation_digest()!=CORE:raise ValueError('Frozen source/content/oldfailure/runtime drift')
    report={'schema':'ark-sim/ch6-snslime-v16-author-evidence/v1','author_checks_passed':True,'core':CORE,'source_at_start':before,'source_at_completion':after,'old_required_failure_preserved':True,'witnesses':records,'generic_peer_gate_signed':False,'complete_source_policies':False,'independent_reviewed':False,'whole_stage_executed':False,'client_verified':False}
    path=DEST/'author.evidence.json';write(path,report);print(json.dumps({'author_checks_passed':True,'witnesses':5,'report_sha256':sha(path)}))
if __name__=='__main__':main()
