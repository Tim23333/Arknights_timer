"""Canonical Nightingale S3 and phantom witnesses with explicit pending gaps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import canonical_summon_witness_support as h
ROOT=h.ROOT
PACKAGE=Path(os.environ.get('CAMPAIGN_SUMMON_PACKAGE',str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_targeting_v2.json')))
CID='char_179_cgbird'
BIRD='unit/support_night_bird'


def base(sp=None,patients=0,dp=50,capacity=8):
    data=h.scene([h.actor(CID,'night',sp=sp)],dp=dp,capacity=capacity,package=PACKAGE)
    data['entities'].append({'id':'unit/night_witness_patient','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'max_hp':10000,'def':0,'mres':10}},
            'resources':{'hp':{'initial':100,'capacity':10000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    for i,pos in enumerate([(4,5),(5,5),(3,5),(4,6)][:patients]):
        data['scenarioDraft']['initialEntities'].append({'definition':'unit/night_witness_patient','instanceAlias':'patient'+str(i),'position':{'row':pos[0],'col':pos[1]}})
    data['entities'].append({'id':'unit/night_witness_actor','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'atk':1000,'max_hp':100000}},'spatial':{},
            'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
            'abilities':['ability/night_witness_'+name for name in ('heal','regen','hurt','kill','arts','physical')]}})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/night_witness_actor','instanceAlias':'probe','position':{'row':0,'col':0}})
    data['selectors'] += [{'id':'selector/night_witness_bird','kind':'selector','region':{'type':'all'},'filters':[{'tag':'night_bird'},{'state':'alive'}],'limit':1},
        {'id':'selector/night_witness_patient','kind':'selector','region':{'type':'all'},'filters':[{'tag':'night_patient'},{'state':'alive'}],'limit':1}]
    for name,op,scale in [('heal','heal',.5),('regen','regenerate',.5),('hurt','damage',5.25),('kill','damage',6),('arts','damage',.1),('physical','damage',.1)]:
        effect={'op':op,'scale':scale}
        if op=='damage':effect['damage_type']=name if name in ('arts','physical') else 'true'
        data['abilities'].append({'id':'ability/night_witness_'+name,'kind':'ability','activation':{'mode':'manual'},
            'selector':'selector/night_witness_patient' if name in ('arts','physical') else 'selector/night_witness_bird',
            'timeline':[{'at':0,'effect':effect}]})
    return data


def spawn(sim,at=0,col=5):h.command(sim,'night','ability/support_night_bird',at=at,position={'row':4,'col':col},facing='right')
def birds(sim):return [e['id'] for e in sim.session.world.entities() if e['definition_id']==BIRD]


def config_sources():
    data=h.read(PACKAGE);host=next(e for e in data['entities'] if e['id']=='unit/'+CID);bird=next(e for e in data['entities'] if e['id']==BIRD)
    row=next(r for r in h.read(ROOT/'packages/campaign/operators.normalized.json')['operators'] if r['character_id']==CID)
    assert host['metadata']['config']==row['config']
    assert host['metadata']['selected_skill_native_id']=='skchr_cgbird_3'
    assert row['selected_skill']['level']['duration']==60
    b=host['components']['attributes']['base'];assert (b['max_hp'],b['atk'],b['def'],b['mres'])==(1624,404,162,5)
    assert host['components']['resources']['bird_cards']['initial']==2
    bb=bird['components']['attributes']['base'];assert (bb['max_hp'],bb['mres'],bb['taunt_level'],bb['block_count'])==(5326,75,1,0)
    assert bird['components']['abilities']==[] and bird['components']['resources']['hp']['parameters']['healing_allowed'] is False
    assert bird['components']['deployable']['capacity']==0 and bird['components']['deployable']['cooldown_seconds']==20
    assert bird['metadata']['source_version_matches_local'] is False
    return {'config_and_bird_source_stats_checked':True,'native_callbacks_and_version_pending':True}


def s3_three_wounded_reselect_repeat():
    sim=h.make(base(sp=120,patients=4));h.command(sim,'night','ability/cgbird_s3')
    sim.advance(27);assert not h.events(sim,'healing.accepted')
    sim.advance(1);heals=h.events(sim,'healing.accepted');assert len(heals)==3
    assert all(e['time']==27 for e in heals)
    for e in heals:h.eq(e['payload']['amount'],404*1.8)
    assert sum(sim.ctx.resources.current('patient'+str(i),'hp')==100 for i in range(4))==1
    sim.advance(86);heals=h.events(sim,'healing.accepted');assert len(heals)==6
    assert {e['payload']['target'] for e in heals}=={sim.session.world.resolve('patient'+str(i)) for i in range(4)}
    assert [e['time'] for e in heals]==[27]*3+[113]*3
    h.eq(sim.ctx.resources.current('night','sp'),0)
    return h.finish(sim)


def resist_and_dodge(seed):
    data=base(sp=120,patients=1)
    patient=data['scenarioDraft']['initialEntities'][1]
    patient['tags']=['player','night_patient']
    patient['components']={'resources':{'hp':{'initial':10000}}}
    sim=h.make(data,seed=seed);h.command(sim,'night','ability/cgbird_s3')
    h.command(sim,'probe','ability/night_witness_arts',at=1);sim.advance(2)
    expected_sample=random.Random(int.from_bytes(hashlib.sha256(json.dumps([seed,'imp'],separators=(',',':')).encode()).digest(),'big')).random()
    assert len(sim.session.random.samples)==1;h.eq(sim.session.random.samples[0]['value'],expected_sample)
    expected=0 if expected_sample<.25 else 100*(1-(10+15)*2.5/100)
    h.eq(sim.ctx.resources.current('patient0','hp'),10000-expected)
    h.command(sim,'probe','ability/night_witness_physical');sim.advance(1)
    h.eq(sim.ctx.resources.current('patient0','hp'),9900-expected)
    assert len(sim.session.random.samples)==1
    return h.finish(sim)


def cards_capacity_atomic():
    data=base(dp=10,capacity=1);data['scenarioDraft']['initialEntities'][0]['deployed']=True
    sim=h.make(data);spawn(sim);spawn(sim,at=2,col=6);spawn(sim,at=4,col=7);sim.advance(5)
    assert len(birds(sim))==2 and all(sim.ctx.alive(uid) for uid in birds(sim))
    h.eq(sim.ctx.resources.current('night','bird_cards'),0);h.eq(sim.ctx.resources.current('system/battle','dp'),0)
    assert len(h.events(sim,'command.rejected'))==1
    owner=sim.session.world.resolve('night');assert all(sim.ctx.get(uid,('ownership','owner'))==owner for uid in birds(sim))
    assert not [e for e in h.events(sim,'ability.started') if e['payload']['source'] in birds(sim)]
    return h.finish(sim)


def failed_dp_and_position():
    sim=h.make(base(dp=4));spawn(sim);sim.advance(1)
    assert not birds(sim);h.eq(sim.ctx.resources.current('night','bird_cards'),2);h.eq(sim.ctx.resources.current('system/battle','dp'),4)
    assert h.events(sim,'command.rejected')
    value=h.finish(sim)
    missing=h.make(base(dp=10));h.command(missing,'night','ability/support_night_bird');missing.advance(1)
    assert not birds(missing);h.eq(missing.ctx.resources.current('night','bird_cards'),2);h.eq(missing.ctx.resources.current('system/battle','dp'),10)
    assert h.events(missing,'command.rejected')
    return {'insufficient_dp':value,'missing_payload':h.finish(missing)}


def bird_loss_heal_free_regeneration():
    sim=h.make(base());spawn(sim);sim.advance(31);uid=birds(sim)[0]
    h.eq(sim.ctx.resources.current(uid,'hp'),5326*.97)
    h.command(sim,'probe','ability/night_witness_heal');sim.advance(1)
    h.eq(sim.ctx.resources.current(uid,'hp'),5326*.97)
    assert h.events(sim,'healing.rejected')
    h.command(sim,'probe','ability/night_witness_regen');sim.advance(2)
    h.eq(sim.ctx.resources.current(uid,'hp'),5326)
    assert not [e for e in h.events(sim,'ability.started') if e['payload']['source']==uid]
    return h.finish(sim)


def bird_drop_death():
    sim=h.make(base());spawn(sim);h.command(sim,'probe','ability/night_witness_hurt',at=2);sim.advance(30)
    uid=birds(sim)[0];h.eq(sim.ctx.resources.current(uid,'hp'),76);assert sim.ctx.alive(uid)
    sim.advance(1);assert not sim.ctx.alive(uid);h.eq(sim.ctx.resources.current(uid,'hp'),0)
    assert sim.ctx.alive('night')
    return h.finish(sim)


def bird_enemy_death_and_owner_retire():
    sim=h.make(base());spawn(sim);h.command(sim,'probe','ability/night_witness_kill',at=2);sim.advance(3)
    assert not sim.ctx.alive(birds(sim)[0]) and sim.ctx.alive('night')
    killed=h.finish(sim)
    other=h.make(base());spawn(other);other.submit({'action':'withdraw','source':'night'},at=2);other.advance(33)
    assert not other.ctx.alive(birds(other)[0])
    assert not h.events(other,'damage.accepted')
    return {'enemy_death':killed,'owner_retirement':h.finish(other)}


def taunt_fixture(blocker=False,filtered=False):
    data=base()
    data['entities'].append({'id':'unit/night_taunt_dummy','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'max_hp':10000,'def':0,'mres':0,'taunt_level':0,'block_count':1 if blocker else 0}},'spatial':{},
            'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}}}})
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/night_taunt_dummy','instanceAlias':'dummy','position':{'row':4,'col':6}})
    probe=next(e for e in data['entities'] if e['id']=='unit/night_witness_actor')
    # Clone the actual production enemy's rule binding, not a test-only score.
    native_enemy=next(e for e in data['entities'] if e['id']=='unit/enemy_1000_gopro')
    probe['rules']=dict(native_enemy.get('rules',{}))
    probe['components']['attributes']['base'].update(attack_interval=.1,attack_speed_ratio=1,block_cost=1)
    if blocker:
        dummy=next(e for e in data['entities'] if e['id']=='unit/night_taunt_dummy')
        dummy['components']['deployable']={'policy':'policy/ark_ground_deploy','terrain':'ground'}
        probe['components']['attributes']['base']['move_speed']=1
        next(i for i in data['scenarioDraft']['initialEntities'] if i['instanceAlias']=='probe')['route']={'motionMode':'WALK','endPosition':{'row':4,'col':10}}
    probe['components']['abilities'].append('ability/night_taunt_attack')
    next(i for i in data['scenarioDraft']['initialEntities'] if i['instanceAlias']=='probe')['position']={'row':4,'col':6 if blocker else 7}
    data['selectors'].append({'id':'selector/night_taunt_all','kind':'selector','region':{'type':'all'},'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/night_taunt_attack','kind':'ability','activation':{'mode':'automatic_attack'},
        'selector':'selector/night_taunt_all','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical','scale':.1}}]})
    if filtered:
        next(e for e in data['entities'] if e['id']=='unit/night_taunt_dummy')['tags'].append('fixture_eligible')
        next(s for s in data['selectors'] if s['id']=='selector/night_taunt_all')['filters'].append({'tag':'fixture_eligible'})
    return data


def taunt_must_affect_default_targeting():
    data=taunt_fixture()
    sim=h.make(data);spawn(sim);sim.advance(1)
    attacks=[e for e in h.events(sim,'attack.accepted') if e['payload']['ability']=='ability/night_taunt_attack']
    assert len(attacks)==1 and attacks[0]['payload']['target']==birds(sim)[0]
    return h.finish(sim)


def taunt_blocked_priority():
    sim=h.make(taunt_fixture(blocker=True));spawn(sim);sim.advance(4)
    source=sim.session.world.resolve('probe');dummy=sim.session.world.resolve('dummy')
    assert sim.ctx.spatial.blocked_by(source)==dummy
    attacks=[e for e in h.events(sim,'attack.accepted') if e['payload']['ability']=='ability/night_taunt_attack']
    assert attacks[-1]['payload']['target']==dummy
    return h.finish(sim)


def taunt_filter_and_retire():
    sim=h.make(taunt_fixture(filtered=True));spawn(sim);sim.advance(1)
    attacks=[e for e in h.events(sim,'attack.accepted') if e['payload']['ability']=='ability/night_taunt_attack']
    assert attacks[0]['payload']['target']==sim.session.world.resolve('dummy')
    filtered=h.finish(sim)
    retired=h.make(taunt_fixture());spawn(retired);retired.submit({'action':'withdraw','source':'night'},at=2);retired.advance(4)
    attacks=[e for e in h.events(retired,'attack.accepted') if e['payload']['ability']=='ability/night_taunt_attack']
    assert attacks[0]['payload']['target']==birds(retired)[0]
    assert attacks[-1]['payload']['target']==retired.session.world.resolve('dummy')
    return {'declared_filter_eligibility':filtered,'source_retirement':h.finish(retired),'native_hidden_or_camouflage_not_authored':True}


def s3_half_open_sixty_seconds():
    data=base(sp=120,patients=1)
    patient=data['scenarioDraft']['initialEntities'][1];patient['tags']=['player','night_patient']
    patient['components']={'resources':{'hp':{'initial':10000}}}
    expected_sample=random.Random(int.from_bytes(hashlib.sha256(b'[11,"imp"]').digest(),'big')).random()
    assert expected_sample>=.25
    sim=h.make(data);h.command(sim,'night','ability/cgbird_s3')
    h.command(sim,'probe','ability/night_witness_arts',at=1799)
    h.command(sim,'probe','ability/night_witness_arts',at=1800)
    sim.advance(1801)
    assert sim.ctx.resources.current('night','mode')==0
    h.eq(sim.ctx.resources.current('patient0','hp'),10000-37.5-75)
    packets=[e for e in h.events(sim,'damage.accepted') if e['payload']['source']==sim.session.world.resolve('probe')]
    assert [(e['time'],e['payload']['amount']) for e in packets]==[(1799,37.5),(1800,75)]
    assert len(sim.session.random.samples)==1
    return h.finish(sim)


CASES={'config_sources':config_sources,'s3_three_wounded_reselect_repeat':s3_three_wounded_reselect_repeat,
    'resist_dodge':lambda:resist_and_dodge(1),'resist_not_dodged':lambda:resist_and_dodge(11),
    'cards_capacity_atomic':cards_capacity_atomic,'failed_dp_and_position':failed_dp_and_position,
    'bird_loss_heal_free_regeneration':bird_loss_heal_free_regeneration,'bird_drop_death':bird_drop_death,
    'bird_enemy_death_and_owner_retire':bird_enemy_death_and_owner_retire,'taunt_must_affect_default_targeting':taunt_must_affect_default_targeting,
    'taunt_blocked_priority':taunt_blocked_priority,'taunt_filter_and_retire':taunt_filter_and_retire}
CASES['s3_half_open_sixty_seconds']=s3_half_open_sixty_seconds


def main():
    global PACKAGE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append',choices=list(CASES))
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/canonical_night_witness.m8_roster.json')
    args=parser.parse_args()
    PACKAGE=args.package.resolve()
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.cgbird.json',ROOT/'packages/campaign/talents.support.json',ROOT/'packages/campaign/animation_bindings.reference.json']
    return h.export(CASES,ROOT/'tests_v2/test_canonical_night.py',Path(__file__),args.output,[CID],sources,args.case,PACKAGE)


if __name__=='__main__':raise SystemExit(main())
