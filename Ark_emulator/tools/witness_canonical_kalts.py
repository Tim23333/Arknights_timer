"""Source-backed canonical Kal'tsit/Mon3tr commands, not a mainline approval."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import canonical_summon_witness_support as h
ROOT=h.ROOT
MON='unit/kalts_mon3tr_model'
CID='char_003_kalts'


def base(sp=None,hp=None,enemy_hp=1000000,near=True,dp=50):
    data=h.scene([h.actor(CID,'host',sp=sp,hp=hp)],dp=dp)
    data['entities'].append({'id':'unit/kalts_witness_enemy','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'max_hp':1000000,'atk':1000,'def':100,'mres':50,'move_speed':1}},
            'resources':{'hp':{'initial':enemy_hp,'capacity':1000000,'role':'health'}},'spatial':{},
            'lifecycle':{'policy':'policy/ark_lifecycle'},'abilities':['ability/kalts_witness_hurt','ability/kalts_witness_kill','ability/kalts_witness_move']}})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/kalts_witness_enemy','instanceAlias':'enemy','position':{'row':4 if near else 0,'col':6 if near else 0}})
    data['selectors'].append({'id':'selector/kalts_witness_mon','kind':'selector','region':{'type':'all'},'filters':[{'tag':'mon3tr'},{'state':'alive'}],'limit':1})
    for name,scale in [('hurt',1),('kill',10)]:
        data['abilities'].append({'id':'ability/kalts_witness_'+name,'kind':'ability','activation':{'mode':'manual'},'selector':'selector/kalts_witness_mon',
            'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':scale}}]})
    data['abilities'].append({'id':'ability/kalts_witness_move','kind':'ability','activation':{'mode':'manual'},'selector':'selector/kalts_witness_mon',
        'timeline':[{'at':0,'effect':{'op':'move','position':{'row':0,'col':0}}}]})
    return data


def summon(sim,owner='host',at=0,row=4,col=5):h.command(sim,owner,'ability/kalts_summon',at=at,position={'row':row,'col':col},facing='right')
def mon(sim,owner='host',alive=True):return h.token(sim,MON,owner,alive)


def config_source():
    data=h.read(h.PACKAGE);unit=next(e for e in data['entities'] if e['id']=='unit/'+CID);pet=next(e for e in data['entities'] if e['id']==MON)
    row=next(r for r in h.read(ROOT/'packages/campaign/operators.normalized.json')['operators'] if r['character_id']==CID)
    assert unit['metadata']['config']==row['config']
    assert unit['metadata']['selected_skill_native_id']=='skchr_kalts_3'
    assert (unit['components']['attributes']['base']['max_hp'],unit['components']['attributes']['base']['atk'])==(1996,468)
    b=pet['components']['attributes']['base'];assert (b['max_hp'],b['atk'],b['def'],b['attack_interval'],b['block_count'])==(5177,1345,389,2,3)
    assert pet['metadata']['native_token_id']=='token_10002_kalts_mon3tr'
    source=h.read(ROOT/'packages/campaign/skills.kalts.json')['manifest']['metadata']['native_source']
    assert source['token_skill_id_slots']==[None,None,None]
    defs={a['id']:a for a in data['abilities']}
    for aid,frame,damage in [('ability/mon3tr_normal_probe',7,1),('ability/mon3tr_true_probe',20,3)]:
        binding=defs[aid]['metadata']['native_attack_binding']
        assert binding['attack_fields']['_damageType']==damage
        assert binding['exact_bindings']['single']['events'][0]['frame']==frame
        assert defs[aid]['metadata']['source_version_matches_local'] is False
    return {'E270_model_stats_checked':True,'frames':[7,20],'external2025_source_2026_correspondence_pending':True,'native_token_skill_id_not_invented':True}


def deploy_atomic():
    sim=h.make(base(near=False,dp=10));summon(sim);sim.advance(1)
    uid=mon(sim);assert sim.ctx.get(uid,('ownership','owner'))==sim.session.world.resolve('host')
    h.eq(sim.ctx.resources.current('system/battle','dp'),0)
    assert sim.ctx.get(uid,('deployable','paid_cost'))==10
    summon(sim,at=1,col=6);sim.advance(1)
    assert mon(sim)==uid and h.events(sim,'command.rejected')
    h.eq(sim.ctx.resources.current('system/battle','dp'),0)
    return h.finish(sim)


def failed_payload_and_capacity():
    data=base(near=False,dp=10)
    data['scenarioDraft']['parameters']['deploy_capacity']=1
    data['scenarioDraft']['initialEntities'][0]['deployed']=True
    sim=h.make(data);summon(sim);sim.advance(1)
    assert h.events(sim,'command.rejected')
    assert not [e for e in sim.session.world.entities() if e['definition_id']==MON]
    h.eq(sim.ctx.resources.current('system/battle','dp'),10)
    h.command(sim,'host','ability/kalts_summon');sim.advance(1)
    assert len(h.events(sim,'command.rejected'))==2
    h.eq(sim.ctx.resources.current('system/battle','dp'),10)
    return h.finish(sim)


def normal_f7_and_s3_f20():
    sim=h.make(base(sp=15));summon(sim);h.command(sim,'host','ability/kalts_host_s3',at=8)
    sim.advance(8)
    packets=h.events(sim,'damage.accepted');assert [(e['time'],e['payload']['amount']) for e in packets]==[(7,1245)]
    sim.advance(72);assert not [e for e in h.events(sim,'damage.accepted') if e['payload']['ability']=='ability/mon3tr_true_probe']
    sim.advance(1)
    true=[e for e in h.events(sim,'damage.accepted') if e['payload']['ability']=='ability/mon3tr_true_probe']
    assert [e['time'] for e in true]==[80]
    h.eq(true[0]['payload']['amount'],1345*(1+2.6*(1-72/600)))
    h.eq(sim.ctx.resources.current('host','sp'),0)
    assert sim.ctx.resources.current(mon(sim),'mode')==1
    return h.finish(sim)


def owned_only_host_gate():
    data=base(sp=15,near=False)
    data['scenarioDraft']['initialEntities'].insert(1,h.actor(CID,'other',row=1,col=1,sp=15))
    sim=h.make(data);summon(sim);h.command(sim,'other','ability/kalts_host_s3');sim.advance(4)
    assert h.events(sim,'command.rejected')
    assert sim.ctx.resources.current(mon(sim),'mode')==0
    h.eq(sim.ctx.resources.current('other','sp'),0)
    assert not [e for e in h.events(sim,'ability.started') if e['payload']['ability']=='ability/kalts_host_s3']
    return h.finish(sim)


def no_token_recovery_and_owner_retire():
    sim=h.make(base(near=False));sim.advance(60);h.eq(sim.ctx.resources.current('host','sp'),0)
    summon(sim,at=60);sim.advance(31);assert sim.ctx.resources.current('host','sp')>0
    uid=mon(sim);sim.submit({'action':'withdraw','source':uid});sim.advance(4)
    assert not sim.ctx.alive(uid)
    assert not [e for e in h.events(sim,'damage.accepted') if e['payload']['source']==uid]
    h.eq(sim.ctx.resources.current('host','sp'),0)
    return h.finish(sim)


def owner_retire_cleanup():
    sim=h.make(base(near=False));summon(sim);sim.advance(1);uid=mon(sim)
    sim.submit({'action':'withdraw','source':'host'});sim.advance(1)
    assert not sim.ctx.alive(uid) and not sim.ctx.alive('host')
    assert not h.events(sim,'damage.accepted')
    return h.finish(sim)


def healing_fixture(own=True,self_hp=None,injure_own=True):
    data=base(near=False,hp=self_hp)
    data['scenarioDraft']['initialEntities'].insert(1,h.actor(CID,'other',row=4,col=8))
    enemy=next(e for e in data['entities'] if e['id']=='unit/kalts_witness_enemy')
    for label,col,scale in [('own',5,.5),('foreign',6,5)]:
        sid='selector/kalts_injure_'+label;aid='ability/kalts_injure_'+label
        enemy['components']['abilities'].append(aid)
        data['selectors'].append({'id':sid,'kind':'selector','region':{'type':'grid_offsets','offsets':[[4,col]],'rotate_with_facing':False},
            'filters':[{'tag':'mon3tr'},{'state':'alive'}],'limit':1})
        data['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},'selector':sid,
            'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':scale}}]})
    enemy['components']['abilities'].append('ability/kalts_injure_both')
    data['abilities'].append({'id':'ability/kalts_injure_both','kind':'ability','activation':{'mode':'manual','on_start':[
        {'op':'damage','selector':'selector/kalts_injure_own','damage_type':'true','scale':.5},
        {'op':'damage','selector':'selector/kalts_injure_foreign','damage_type':'true','scale':5}]},'timeline':[]})
    sim=h.make(data)
    if own:summon(sim)
    summon(sim,'other',col=6)
    h.command(sim,'enemy','ability/kalts_injure_both' if own and self_hp is None and injure_own else 'ability/kalts_injure_foreign',at=1)
    return sim


def healing_prefers_self():
    # Summon's empty manual cast blocks host attacks in tick0; first ordinary
    # heal starts1. Injury effects in tick1 become candidates for tick2 planning.
    sim=healing_fixture(self_hp=1000);sim.advance(15)
    host=sim.session.world.resolve('host');heals=[e for e in h.events(sim,'healing.accepted') if e['payload']['source']==host]
    assert len(heals)==1 and heals[0]['time']==14 and heals[0]['payload']['target']==host
    h.eq(heals[0]['payload']['amount'],468);h.eq(sim.ctx.resources.current('host','hp'),1468)
    h.eq(sim.ctx.resources.current(mon(sim,'other'),'hp'),177)
    return h.finish(sim)


def healing_prefers_owned_mon():
    sim=healing_fixture();sim.advance(21)
    uid=mon(sim);host=sim.session.world.resolve('host')
    heals=[e for e in h.events(sim,'healing.accepted') if e['payload']['source']==host]
    assert len(heals)==1 and heals[0]['time']==20 and heals[0]['payload']['target']==uid
    h.eq(sim.ctx.resources.current(uid,'hp'),5145)
    h.eq(sim.ctx.resources.current(mon(sim,'other'),'hp'),177)
    return h.finish(sim)


def healing_foreign_fallback():
    sim=healing_fixture(injure_own=False);sim.advance(28)
    uid=mon(sim,'other');host=sim.session.world.resolve('host')
    heals=[e for e in h.events(sim,'healing.accepted') if e['payload']['source']==host]
    assert len(heals)==1 and heals[0]['time']==27 and heals[0]['payload']['target']==uid
    h.eq(sim.ctx.resources.current(uid,'hp'),645)
    return h.finish(sim)


def no_owned_token_must_not_interrupt_ordinary_heal():
    sim=healing_fixture(own=False);sim.advance(28)
    uid=mon(sim,'other');host=sim.session.world.resolve('host')
    heals=[e for e in h.events(sim,'healing.accepted') if e['payload']['source']==host]
    assert len(heals)==1 and heals[0]['time']==27 and heals[0]['payload']['target']==uid
    h.eq(sim.ctx.resources.current(uid,'hp'),645)
    return h.finish(sim)


def death_rattle():
    sim=h.make(base());summon(sim);h.command(sim,'enemy','ability/kalts_witness_kill',at=1);sim.advance(2)
    uid=mon(sim,alive=False);assert not sim.ctx.alive(uid)
    packets=[e for e in h.events(sim,'damage.accepted') if e['payload']['source']==uid]
    assert len(packets)==1 and packets[0]['time']==1 and packets[0]['payload']['amount']==1200
    assert sim.ctx.buffs.controls('enemy')['attack'] is False
    sim.advance(89);assert sim.ctx.buffs.controls('enemy')['attack'] is True
    return h.finish(sim)


def withdraw_not_death_and_cooldown():
    sim=h.make(base());summon(sim);sim.advance(1);uid=mon(sim)
    sim.submit({'action':'withdraw','source':uid});sim.advance(1)
    assert not sim.ctx.alive(uid)
    assert not h.events(sim,'damage.accepted')
    summon(sim,at=2);sim.advance(1)
    assert h.events(sim,'command.rejected')
    h.eq(sim.ctx.resources.current('system/battle','dp'),45)
    return h.finish(sim)


def no_kill_penalty():
    sim=h.make(base(sp=15,near=False));summon(sim);h.command(sim,'host','ability/kalts_host_s3');sim.advance(600)
    uid=mon(sim);h.eq(sim.ctx.resources.current(uid,'hp'),5177)
    sim.advance(1);h.eq(sim.ctx.resources.current(uid,'hp'),2588.5)
    assert sim.ctx.resources.current(uid,'mode')==0 and sim.ctx.resources.current(uid,'no_kill')==0
    return h.finish(sim)


def own_kill_skips_penalty():
    sim=h.make(base(sp=15,enemy_hp=100));summon(sim);h.command(sim,'host','ability/kalts_host_s3');sim.advance(21)
    uid=mon(sim);assert sim.ctx.resources.current(uid,'no_kill')==0
    kills=h.events(sim,'combat.kill');assert len(kills)==1 and kills[0]['payload']['source']==uid
    sim.advance(580);h.eq(sim.ctx.resources.current(uid,'hp'),5177)
    return h.finish(sim)


CASES={'config_source':config_source,'deploy_atomic':deploy_atomic,'failed_payload_and_capacity':failed_payload_and_capacity,
    'normal_f7_and_s3_f20':normal_f7_and_s3_f20,'owned_only_host_gate':owned_only_host_gate,
    'no_token_recovery_and_owner_retire':no_token_recovery_and_owner_retire,'death_rattle':death_rattle,
    'owner_retire_cleanup':owner_retire_cleanup,'healing_prefers_self':healing_prefers_self,
    'healing_prefers_owned_mon':healing_prefers_owned_mon,'healing_foreign_fallback':healing_foreign_fallback,
    'no_owned_token_must_not_interrupt_ordinary_heal':no_owned_token_must_not_interrupt_ordinary_heal,
    'withdraw_not_death_and_cooldown':withdraw_not_death_and_cooldown,'no_kill_penalty':no_kill_penalty,'own_kill_skips_penalty':own_kill_skips_penalty}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append',choices=list(CASES))
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/canonical_kalts_witness.m8_roster.json')
    args=parser.parse_args()
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.kalts.json',ROOT/'packages/campaign/talents.support.json',ROOT/'packages/campaign/roster.profiles.json']
    return h.export(CASES,ROOT/'tests_v2/test_canonical_kalts.py',Path(__file__),args.output,[CID],sources,args.case)


if __name__=='__main__':raise SystemExit(main())
