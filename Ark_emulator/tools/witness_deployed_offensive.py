"""Extended canonical offensive actor witnesses, with frozen endpoint helper."""
from copy import deepcopy
import argparse
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import witness_deployed_six as h


def high_tile(data,row,col):
    """Explicit synthetic terrain for a real ranged-card deployment."""
    terrain=data['scenarioDraft']['map']
    if 'tiles' not in terrain:
        terrain['tiles']=[{'tileKey':'tile_floor','passableMask':3,'buildableType':1}
            for _ in range(terrain['rows']*terrain['cols'])]
    terrain['tiles'][row*terrain['cols']+col]={'tileKey':'tile_wall','passableMask':2,'buildableType':2,'heightType':1}


def case_bpipe_splash_excludes_primary():
    seed=11;sim=h.make(h.scene([h.actor('bpipe',40)],enemies=[(4,5),(4,5)]),seed)
    h.command(sim,'bpipe','ability/campaign_bpipe_s3');sim.advance(21)
    expected=h.samples(seed,3);first=sim.session.world.resolve('enemy0');second=sim.session.world.resolve('enemy1')
    hits=h.events(sim,'damage.accepted','bpipe','ability/campaign_bpipe_triple')
    primary=[e for e in hits if e['payload']['target']==first];splash=[e for e in hits if e['payload']['target']==second]
    assert [e['time'] for e in primary]==[14,17,20]
    for e,v in zip(primary,expected):h.eq(e['payload']['amount'],(1859 if v<.25 else 1430)-50)
    assert [e['time'] for e in splash]==[t for t,v in zip((14,17,20),expected) if v<.25]
    for e in splash:h.eq(e['payload']['amount'],1809)
    assert len(sim.session.random.samples)==3
    return h.finish(sim,{'primary_packet_count':3,'critical_samples':expected,'splash_damage':1809,
        'one_extra_target_per_proc':True,'no_recursive_sampling':True})


def case_bpipe_defense_block_and_expiry():
    data=h.scene([h.actor('bpipe',40,deployed=True)],enemies=[(4,4),(4,4)])
    enemy=next(e for e in data['entities'] if e['id']=='unit/deployed_witness_enemy')
    enemy['components']['attributes']['base']['atk']=1000
    enemy['components']['abilities']=['ability/offensive_incoming']
    for item in data['scenarioDraft']['initialEntities'][1:]:
        item['route']={'motionMode':'WALK','endPosition':{'row':4,'col':8},'checkpoints':[]}
    data['selectors'].append({'id':'selector/offensive_player','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'player'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/offensive_incoming','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/offensive_player','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical'}}]})
    sim=h.make(data);h.command(sim,'bpipe','ability/campaign_bpipe_s3')
    h.command(sim,'enemy0','ability/offensive_incoming',1);h.command(sim,'enemy0','ability/offensive_incoming',600)
    sim.advance(599)
    blocker=sim.session.world.resolve('bpipe')
    assert all(sim.ctx.get('enemy'+str(i),('runtime','blocked_by'))==blocker for i in (0,1))
    incoming=h.events(sim,'damage.accepted','enemy0','ability/offensive_incoming')
    assert len(incoming)==1;h.eq(incoming[0]['payload']['amount'],194.8)
    h.eq(sim.ctx.resources.current('bpipe','sp'),0)
    sim.advance(2)
    assert sum(sim.ctx.get('enemy'+str(i),('runtime','blocked_by'))==blocker for i in (0,1))==1
    incoming=h.events(sim,'damage.accepted','enemy0','ability/offensive_incoming')
    h.eq(incoming[-1]['payload']['amount'],634)
    h.eq(sim.ctx.resources.current('bpipe','hp'),1487.2)
    return h.finish(sim,{'defense_active':805.2,'defense_restored':366,'incoming_atk':1000,
        'damage_tick1':194.8,'damage_tick600':634,'block_count_before_after':[2,1],'skill_end_tick':600})


def case_bpipe_deck_sp_and_refund_cap():
    data=h.scene([]);sim=h.make(data)
    sim.submit({'action':'deploy','entity':'unit/char_151_myrtle','alias':'myrtle',
        'position':{'row':4,'col':4},'facing':'right'},at=0)
    sim.advance(1);h.eq(sim.ctx.resources.current('myrtle','sp'),16)
    assert not any(e['definition_id']=='unit/char_222_bpipe' for e in sim.session.world.entities())
    deck_result=h.finish(sim,{'Myrtle_native_init':10,'deck_Bagpipe_bonus':6,'Bagpipe_not_deployed':True})
    sim=h.make(h.scene([]))
    sim.submit({'action':'deploy','entity':'unit/char_222_bpipe','alias':'bpipe',
        'position':{'row':4,'col':4},'facing':'right'},at=0)
    sim.submit({'action':'withdraw','source':'bpipe'},at=2)
    sim.submit({'action':'deploy','entity':'unit/char_222_bpipe','alias':'bpipe2',
        'position':{'row':4,'col':4},'facing':'right'},at=2102)
    sim.submit({'action':'withdraw','source':'bpipe2'},at=2104)
    sim.advance(2105)
    returned=[e for e in h.events(sim,'resource.changed') if e['payload']['resource']=='dp' and e['payload']['delta']>1]
    assert [e['payload']['delta'] for e in returned]==[13,13]
    result=h.finish(sim,{'raw_cost':13,'first_refund':13,'second_refund_raw_cap':13,'redeploy_seconds':70,'second_deploy_tick':2102})
    result['deck_only_scenario']=deck_result
    return result


def case_angel_force_and_empty_auto():
    sim=h.make(h.scene([h.actor('angel',30)]))
    h.command(sim,'angel','ability/campaign_angel_s3');sim.advance(31)
    assert len(h.events(sim,'command.rejected'))==1
    assert len(h.events(sim,'ability.started','angel','ability/campaign_angel_s3'))==1
    h.eq(sim.ctx.resources.current('angel','sp'),0)
    assert not h.events(sim,'projectile.launched') and not h.events(sim,'damage.accepted')
    return h.finish(sim,{'manual_force_rejected':True,'auto_paid_30':True,'no_targets_no_fake_packets':True})


def case_angel_retargets_after_first_death():
    data=h.scene([h.actor('angel',30)],enemies=[(4,5),(4,5)])
    data['scenarioDraft']['initialEntities'][1]['components']={'resources':{'hp':{'initial':1}}}
    sim=h.make(data);sim.advance(19)
    launches=h.events(sim,'projectile.launched','angel');first=sim.session.world.resolve('enemy0');second=sim.session.world.resolve('enemy1')
    assert [e['payload']['target'] for e in launches]==[first]+[second]*4
    hits=h.events(sim,'damage.accepted','angel','ability/campaign_angel_burst')
    assert len(hits)==5;h.eq(hits[0]['payload']['amount'],1)
    for e in hits[1:]:h.eq(e['payload']['amount'],657.762)
    assert len(h.events(sim,'attack.accepted','angel','ability/campaign_angel_burst'))==1
    return h.finish(sim,{'captured_first_launch':first,'remaining_launches_reselect':second,'attack_event_count':1})


def case_angel_blessing_deploy_and_retire():
    seed=11;data=h.scene([h.actor('myrtle',0,hp=1000),h.actor('plosis',0,hp=1200,row=5)])
    high_tile(data,4,3)
    sim=h.make(data,seed);sim.submit({'action':'deploy','entity':'unit/char_103_angel','alias':'angel',
        'position':{'row':4,'col':3},'facing':'right'},at=0)
    sim.submit({'action':'withdraw','source':'angel'},at=2);sim.advance(1)
    value=h.samples(seed,1)[0];friend=('myrtle','plosis')[math.floor(value*2)]
    blessed=[name for name in ('myrtle','plosis') if any(b['definition']=='buff/talent_angel_friend'
        for b in sim.ctx.get(name,('buffs','instances'),[]))]
    assert blessed==[friend] and len(sim.session.random.samples)==1;h.eq(sim.session.random.samples[0]['value'],value)
    h.eq(sim.ctx.resources.current('angel','hp'),1598)
    friend_hp=1000 if friend=='myrtle' else 1200;h.eq(sim.ctx.resources.current(friend,'hp'),friend_hp)
    sim.advance(2)
    assert not any(b['definition']=='buff/talent_angel_friend' for name in ('myrtle','plosis')
        for b in sim.ctx.get(name,('buffs','instances'),[]))
    return h.finish(sim,{'self_base_HP':1598,'self_maxHP_multiplier':1.1,'current_HP_policy':'absolute/clamped',
        'one_friend':friend,'friend_sample':value,'source_retire_removes_friend_modifier':True})


def case_eyja_six_limit_and_filter():
    seed=11;positions=[(4,5),(4,6),(4,7),(5,4),(5,5),(3,4),(3,5),(4,5),(0,0)]
    data=h.scene([h.actor('amgoat',80)],enemies=positions)
    data['scenarioDraft']['initialEntities'][8]['components']={'resources':{'hp':{'initial':0}}}
    sim=h.make(data,seed);h.command(sim,'amgoat','ability/campaign_amgoat_s3');sim.advance(16)
    expected=h.samples(seed,12);remaining=[sim.session.world.resolve('enemy'+str(i)) for i in range(7)];selected=[]
    for sample in expected[:6]:selected.append(remaining.pop(min(len(remaining)-1,math.floor(sample*len(remaining)))))
    launches=[e for e in h.events(sim,'projectile.launched','amgoat') if e['time']==0]
    assert [e['payload']['target'] for e in launches]==selected
    hits=[e for e in h.events(sim,'damage.accepted','amgoat','ability/campaign_amgoat_probe_packet') if e['time']<=15]
    assert len(hits)==6
    for e in hits:h.eq(e['payload']['amount'],1732.4)
    assert len(sim.session.random.samples)==12
    for a,b in zip(sim.session.random.samples,expected):h.eq(a['value'],b)
    return h.finish(sim,{'alive_in_range_candidates':7,'limit':6,'first_selected_ids':selected,
        'dead_and_outside_filtered':True,'damage_per_packet':1732.4,'two_signals_draws':12})


def case_eyja_empty_half_open():
    sim=h.make(h.scene([h.actor('amgoat',80)]));h.command(sim,'amgoat','ability/campaign_amgoat_s3')
    sim.advance(450);h.eq(sim.ctx.resources.current('amgoat','mode'),1);h.eq(sim.ctx.resources.current('amgoat','sp'),0)
    assert not sim.session.random.samples and not h.events(sim,'damage.accepted')
    sim.advance(31);h.eq(sim.ctx.resources.current('amgoat','mode'),0);h.eq(sim.ctx.resources.current('amgoat','sp'),1)
    return h.finish(sim,{'duration_ticks':450,'empty_targets_no_draws_or_damage':True,'SP_after_next_full_period':1})


def case_eyja_deploy_float_and_caster_aura_retire():
    seed=11;data=h.scene([],enemies=[(4,5)])
    high_tile(data,4,4)
    data['entities'].append({'id':'unit/offensive_caster_friend','kind':'entity','tags':['player','profession:CASTER'],
        'components':{'attributes':{'base':{'atk':100,'max_hp':10000,'def':0,'mres':0}},
            'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},'spatial':{},'abilities':['ability/offensive_caster_packet']}})
    data['scenarioDraft']['initialEntities'].insert(0,{'definition':'unit/offensive_caster_friend','instanceAlias':'friend','position':{'row':5,'col':4}})
    data['selectors'].append({'id':'selector/offensive_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/offensive_caster_packet','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/offensive_enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true'}}]})
    sim=h.make(data,seed);sim.submit({'action':'deploy','entity':'unit/char_180_amgoat','alias':'amgoat',
        'position':{'row':4,'col':4},'facing':'right'},at=0)
    h.command(sim,'friend','ability/offensive_caster_packet',1)
    sim.submit({'action':'withdraw','source':'amgoat'},at=2);h.command(sim,'friend','ability/offensive_caster_packet',3)
    sim.advance(1);sample=h.samples(seed,1)[0]
    h.eq(sim.ctx.resources.current('amgoat','sp'),55+7+9*sample)
    assert len(sim.session.random.samples)==1;h.eq(sim.session.random.samples[0]['value'],sample)
    sim.advance(3);hits=h.events(sim,'damage.accepted','friend','ability/offensive_caster_packet')
    assert [e['time'] for e in hits]==[1,3]
    for e,amount in zip(hits,(114,100)):h.eq(e['payload']['amount'],amount)
    return h.finish(sim,{'native_initial_SP':55,'random_SP_gain':7+9*sample,'sample':sample,
        'caster_damage_before_after_source_retire':[114,100]})


CASES={name[5:]:value for name,value in list(globals().items()) if name.startswith('case_') and callable(value)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--package',type=Path,default=h.PACKAGE);parser.add_argument('--case',action='append');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();h.PACKAGE=args.package.resolve();sys.path.insert(0,str(args.runtime_root.resolve()))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    assert Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve())
    files=[Path(__file__),ROOT/'tools/witness_deployed_six.py',h.PACKAGE]
    before={str(p):h.sha(p) for p in files};core=implementation_digest();selected=args.case or list(CASES)
    result={'schema':'ark-sim/deployed-offensive-witnesses/v1','passed':False,'implementation_sha256':core,
        'input_package':str(h.PACKAGE),'input_package_sha256':h.sha(h.PACKAGE),'selected_cases':selected,
        'cases':{},'runtime_module':ark_sim.__file__,'identity_at_start':before,'formal_stage_approved':False}
    for name in selected:
        try:result['cases'][name]=CASES[name]();print(json.dumps({'case':name,'passed':True}),flush=True)
        except Exception as error:
            result['failure']={'case':name,'error':repr(error)}
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            raise
    after={str(p):h.sha(p) for p in files};assert before==after and core==implementation_digest()
    result.update(passed=True,identity_stable=True,identity_at_completion=after,
        tests=[{'path':p.relative_to(ROOT).as_posix(),'source_sha256':h.sha(p),'result':'passed'} for p in files[:2]])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


if __name__=='__main__':main()
