"""Canonical Weedy/cannon source-profile witnesses, not native approval."""
import argparse
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import canonical_summon_witness_support as h
ROOT=h.ROOT
CID='char_400_weedy'
CANNON='unit/campaign_weedy_cannon'
SKILL='ability/campaign_weedy_s3'
RUPTURE='buff/campaign_weedy_rupture'


def base(sp=None,mass=0,enemy=True,dp=50):
    data=h.scene([h.actor(CID,'weedy',sp=sp)],dp=dp)
    data['entities'].append({'id':'unit/weedy_witness_enemy','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'atk':100,'max_hp':1000000,'def':100,'mres':20,'mass_level':mass,'move_speed':.3,'block_cost':1}},
            'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},
            'abilities':['ability/weedy_witness_remove']}})
    data['abilities'].append({'id':'ability/weedy_witness_remove','kind':'ability','activation':{'mode':'manual',
        'on_start':[{'op':'remove_buff','target':'source','buff':RUPTURE}]},'timeline':[]})
    if enemy:data['scenarioDraft']['initialEntities'].append({'definition':'unit/weedy_witness_enemy','instanceAlias':'enemy','position':{'row':4,'col':6}})
    return data


def deploy(sim,at=0,col=5):h.command(sim,'weedy','ability/campaign_weedy_deploy_cannon',at=at,position={'row':4,'col':col},facing='right')
def cannon(sim,alive=True):return h.token(sim,CANNON,'weedy',alive)
def hits(sim,ability):return [e for e in h.events(sim,'damage.accepted') if e['payload'].get('ability')==ability]
def distance_damage(sim):return sum(e['payload']['amount'] for e in h.events(sim,'damage.accepted') if e['payload'].get('ability') is None)


def config_source():
    data=h.read(h.PACKAGE);host=next(e for e in data['entities'] if e['id']=='unit/'+CID);pet=next(e for e in data['entities'] if e['id']==CANNON)
    row=next(r for r in h.read(ROOT/'packages/campaign/operators.normalized.json')['operators'] if r['character_id']==CID)
    assert host['metadata']['config']==row['config'] and host['metadata']['selected_skill_native_id']=='skchr_weedy_3'
    b=host['components']['attributes']['base'];assert (b['max_hp'],b['atk'],b['def'])==(2027,693,424)
    b=pet['components']['attributes']['base'];assert (b['atk'],b['attack_interval'],b['force_bonus'])==(561,2.4,1)
    assert pet['components']['deployable']['capacity']==0 and pet['components']['deployable']['cooldown_seconds']==35
    defs={a['id']:a for a in data['abilities']}
    assert defs[SKILL]['timeline'][0]['at_seconds']==10/30 and defs[SKILL]['parameters']['wait_for_projectiles'] is True
    assert defs['ability/support_cannon_normal']['timeline'][0]['at_seconds']==1/30
    return {'stats_frames_costs_checked':True,'native_push_curve_and_2025_token_correspondence_pending':True}


def normal_f1_travel_and_payment():
    data=base();data['scenarioDraft']['parameters']['deploy_capacity']=1;data['scenarioDraft']['initialEntities'][0]['deployed']=True
    sim=h.make(data);deploy(sim);sim.advance(4)
    assert not hits(sim,'ability/support_cannon_normal')
    sim.advance(1);normal=hits(sim,'ability/support_cannon_normal')
    assert len(normal)==1 and normal[0]['time']==4;h.eq(normal[0]['payload']['amount'],561-100)
    h.eq(sim.ctx.resources.current('system/battle','dp'),45)
    assert sim.ctx.get(cannon(sim),('deployable','paid_cost'))==5
    return h.finish(sim)


def sp_near_and_far():
    near=h.make(base(sp=0,enemy=False));deploy(near);near.advance(90)
    h.eq(near.ctx.resources.current('weedy','sp'),2)
    near.advance(1);h.eq(near.ctx.resources.current('weedy','sp'),4)
    first=h.finish(near)
    far=h.make(base(sp=0,enemy=False));deploy(far,col=9);far.advance(91)
    h.eq(far.ctx.resources.current('weedy','sp'),3)
    return {'near':first,'outside_manhattan4':h.finish(far)}


def host_and_owned_s3_link():
    sim=h.make(base(sp=33,mass=10));deploy(sim);h.command(sim,'weedy',SKILL,at=2);sim.advance(21)
    own=hits(sim,'ability/campaign_weedy_cannon_s3');host=hits(sim,SKILL)
    assert len(own)==len(host)==1
    assert own[0]['time']==6 and host[0]['time']==20
    h.eq(own[0]['payload']['amount'],561*3.5*.8);h.eq(host[0]['payload']['amount'],693*3.5*.8)
    assert own[0]['payload']['source']==cannon(sim)
    costs=[e for e in h.events(sim,'resource.changed') if e['payload'].get('reason')=='ability_cost' and e['payload']['resource']=='sp']
    assert len(costs)==1 and costs[0]['payload']['delta']==-33
    active=[b for b in sim.ctx.get('enemy',('buffs','instances')) if b['definition']==RUPTURE]
    assert len(active)==1 and active[0]['stacks']==1 and active[0]['expires_at']==6+480
    h.eq(distance_damage(sim),0)
    return h.finish(sim)


def s3_push_and_path_conservation():
    sim=h.make(base(sp=33));h.command(sim,'weedy',SKILL);sim.advance(65)
    cast=hits(sim,SKILL);assert len(cast)==1 and cast[0]['time']==18;h.eq(cast[0]['payload']['amount'],1940.4)
    actual=sim.ctx.get('enemy',('spatial','distance_travelled'))
    h.eq(actual,3.33058);h.eq(sim.ctx.get('enemy',('spatial','position'))['col'],6+3.33058)
    h.eq(distance_damage(sim),3.33058*1200)
    return h.finish(sim)


def final_unflushed_tail():
    sim=h.make(base(sp=33));h.command(sim,'weedy',SKILL);h.command(sim,'enemy','ability/weedy_witness_remove',at=21);sim.advance(22)
    # Pure model plan: D3.33058, T2D/5.8 ->35 quantized steps. Two steps before
    # command21 remove the lease; remove must charge its otherwise pending tail.
    steps=math.ceil((2*3.33058/5.8)*30);assert steps==35
    h.eq(distance_damage(sim),2*3.33058/35*1200)
    assert not [b for b in sim.ctx.get('enemy',('buffs','instances')) if b['definition']==RUPTURE]
    return h.finish(sim)


def wall_clips_actual_distance():
    data=base(sp=33);tiles=[{'tileKey':'tile_floor','passableMask':1,'buildableType':1} for _ in range(9*12)]
    tiles[4*12+7]={'tileKey':'tile_wall','passableMask':0,'buildableType':0};data['scenarioDraft']['map']['tiles']=tiles
    sim=h.make(data);h.command(sim,'weedy',SKILL);sim.advance(70)
    actual=sim.ctx.get('enemy',('spatial','distance_travelled'));assert .49<actual<.5
    h.eq(distance_damage(sim),actual*1200)
    assert distance_damage(sim)<=600+1e-6 and distance_damage(sim)>588 # HP subtraction float error only.
    return h.finish(sim)


def cannon_lifetime_and_cooldown():
    sim=h.make(base(enemy=False));deploy(sim);sim.advance(600);uid=cannon(sim)
    assert sim.ctx.alive(uid)
    sim.advance(1);assert not sim.ctx.alive(uid)
    balance=sim.ctx.resources.current('system/battle','dp');deploy(sim,at=601);sim.advance(1)
    assert h.events(sim,'command.rejected');h.eq(sim.ctx.resources.current('system/battle','dp'),balance)
    return h.finish(sim)


def owner_retire_cleanup():
    sim=h.make(base(enemy=False));deploy(sim);sim.advance(1);uid=cannon(sim)
    sim.submit({'action':'withdraw','source':'weedy'});sim.advance(92)
    assert not sim.ctx.alive(uid) and not sim.ctx.alive('weedy')
    assert not h.events(sim,'damage.accepted')
    return h.finish(sim)


def empty_target_explicit_profile():
    sim=h.make(base(sp=33,enemy=False));h.command(sim,'weedy',SKILL);sim.advance(11)
    assert not h.events(sim,'command.rejected')
    h.eq(sim.ctx.resources.current('weedy','sp'),0)
    assert not h.events(sim,'projectile.launched') and not h.events(sim,'damage.accepted')
    result=h.finish(sim)
    result['profile']='empty-target allowed/pays33/no-forward-bullet model; native forward-projectile/invalid callbacks remain pending'
    return result


CASES={'config_source':config_source,'normal_f1_travel_and_payment':normal_f1_travel_and_payment,'sp_near_and_far':sp_near_and_far,
    'host_and_owned_s3_link':host_and_owned_s3_link,'s3_push_and_path_conservation':s3_push_and_path_conservation,
    'final_unflushed_tail':final_unflushed_tail,'wall_clips_actual_distance':wall_clips_actual_distance,
    'cannon_lifetime_and_cooldown':cannon_lifetime_and_cooldown,'owner_retire_cleanup':owner_retire_cleanup,
    'empty_target_explicit_profile':empty_target_explicit_profile}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append',choices=list(CASES))
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/canonical_weedy_witness.m8_roster.json')
    args=parser.parse_args()
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.weedy.json',ROOT/'packages/campaign/talents.support.json']
    return h.export(CASES,ROOT/'tests_v2/test_canonical_weedy.py',Path(__file__),args.output,[CID],sources,args.case)


if __name__=='__main__':raise SystemExit(main())
