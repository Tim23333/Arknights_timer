"""Independent endpoints for the six actors deployed by the first-stage script."""
from copy import deepcopy
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PACKAGE = Path(os.environ.get('CAMPAIGN_DEPLOYED_PACKAGE', str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')))
LAST_SIM = None
IDS = {'myrtle':'char_151_myrtle','bpipe':'char_222_bpipe','angel':'char_103_angel',
       'plosis':'char_128_plosis','amgoat':'char_180_amgoat','demkni':'char_202_demkni'}


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def eq(value, expected): assert abs(value-expected) < 1e-7, (value,expected)


def actor(name,sp=None,hp=None,row=4,col=4,deployed=False):
    item={'definition':'unit/'+IDS[name],'instanceAlias':name,'position':{'row':row,'col':col},'facing':'right','deployed':deployed}
    resources={}
    if sp is not None: resources['sp']={'initial':sp}
    if hp is not None: resources['hp']={'initial':hp}
    if resources:item['components']={'resources':resources}
    return item


def scene(initial,enemies=(),patients=()):
    data=read(PACKAGE)
    s=data['scenarioDraft'];s.update(id='scenario/canonical_deployed_six',map={'rows':9,'cols':12},
        waves=[],scheduledEffects=[],objectives={},initialEntities=deepcopy(initial))
    s.pop('timeline',None);s['resources']['dp']['initial']=50
    data['entities'] += [
        {'id':'unit/deployed_witness_enemy','kind':'entity','tags':['enemy','ground'],
         'components':{'attributes':{'base':{'atk':100,'max_hp':1000000,'def':50,'mres':0,'move_speed':0,'block_cost':1}},
          'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}},
        {'id':'unit/deployed_witness_patient','kind':'entity','tags':['player','ground'],
         'components':{'attributes':{'base':{'max_hp':100000,'def':0,'mres':0}},
          'resources':{'hp':{'initial':100,'capacity':100000,'role':'health'}},'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}]
    for i,position in enumerate(enemies):
        s['initialEntities'].append({'definition':'unit/deployed_witness_enemy','instanceAlias':'enemy'+str(i),
            'position':{'row':position[0],'col':position[1]}})
    for i,position in enumerate(patients):
        s['initialEntities'].append({'definition':'unit/deployed_witness_patient','instanceAlias':'patient'+str(i),
            'position':{'row':position[0],'col':position[1]}})
    return data


def make(data,seed=11):
    global LAST_SIM
    from ark_sim import Compiler,Engine
    LAST_SIM = Engine.create(Compiler().compile(data),seed=seed)
    return LAST_SIM


def command(sim,name,ability,at=0):
    sim.submit({'action':'skill','source':name,'ability':ability},at=at)


def events(sim,kind,source=None,ability=None):
    ref=sim.session.world.resolve(source) if source else None
    return [e for e in sim.session.events if e['type']==kind and
        (ref is None or e['payload'].get('source')==ref) and (ability is None or e['payload'].get('ability')==ability)]


def samples(seed,count):
    derived=int.from_bytes(hashlib.sha256(json.dumps([seed,'imp'],separators=(',',':')).encode()).digest(),'big')
    generator=random.Random(derived)
    return [generator.random() for _ in range(count)]


def finish(sim,expected):
    from ark_sim import Engine
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    checkpoint=sim.checkpoint();restored=Engine.restore(sim.program,checkpoint)
    sim.advance(2);restored.advance(2)
    assert sim.snapshot()==restored.snapshot()
    assert sim.snapshot()==replay(sim.program,sim.export_replay()).snapshot()
    types={'ability.started','ability.finished','ability.effect','attack.accepted','damage.accepted','healing.accepted',
        'regeneration.accepted','resource.changed','buff.applied','buff.removed','combat.kill','command.accepted','command.rejected','projectile.launched'}
    return {'expected':expected,'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
        'checkpoint_equal':True,'replay_equal':True,'tick':sim.session.time,
        'events':[thaw(e) for e in sim.session.events if e['type'] in types],
        'random_samples':thaw(sim.session.random.samples),'commands':sim.export_replay(),
        'fixture_initial_state':thaw(sim.program.scenario),
        'entity_identities':[{'id':e['id'],'definition':e['definition_id']} for e in sim.session.world.entities()],
        'actor_runtime':[{'id':e['id'],'definition':e['definition_id'],
            'resources':{key:value['current'] for key,value in e['components'].get('resources',{}).items()},
            'buff_instances':thaw(e['components'].get('buffs',{}).get('instances',[])),
            'attribute_base':thaw(e['components'].get('attributes',{}).get('base',{})),
            'attribute_modifiers':thaw(e['components'].get('attributes',{}).get('modifiers',[]))}
            for e in sim.session.world.entities() if 'campaign_roster' in e['tags']]}


def case_myrtle_dp_heal_window():
    sim=make(scene([actor('myrtle',24)],patients=[(4,5)]))
    command(sim,'myrtle','ability/campaign_myrtle_s2');sim.advance(481)
    heals=events(sim,'healing.accepted','myrtle')
    assert [e['time'] for e in heals]==[16+30*i for i in range(16)]
    assert [e['payload']['amount'] for e in heals]==[260]*16
    eq(sim.ctx.resources.current('patient0','hp'),4260)
    ref=sim.session.world.resolve('myrtle');dp=[e for e in events(sim,'resource.changed') if e['payload']['resource']=='dp' and e['payload']['source']==ref]
    assert [e['time'] for e in dp]==list(range(30,481,30))
    assert [e['payload']['delta'] for e in dp]==[1]*16
    eq(sim.ctx.resources.current('myrtle','sp'),0)
    return finish(sim,{'heal_amount':260,'heal_ticks':[16+30*i for i in range(16)],'skill_dp_total':16,'duration_ticks':480})


def case_bpipe_triple_rng():
    seed=11;sim=make(scene([actor('bpipe',40)],enemies=[(4,5)]),seed)
    command(sim,'bpipe','ability/campaign_bpipe_s3');sim.advance(21)
    actual=events(sim,'damage.accepted','bpipe','ability/campaign_bpipe_triple')
    expected_samples=samples(seed,3);expected=[1859-50 if v<.25 else 1430-50 for v in expected_samples]
    assert [e['time'] for e in actual]==[14,17,20]
    for event,amount in zip(actual,expected):eq(event['payload']['amount'],amount)
    assert len(sim.session.random.samples)==3
    for actual_sample,expected_sample in zip(sim.session.random.samples,expected_samples):eq(actual_sample['value'],expected_sample)
    eq(sim.ctx.resources.current('bpipe','sp'),0)
    return finish(sim,{'base_atk':650,'skill_atk':1430,'skill_def':805.2,'packet_ticks':[14,17,20],
        'critical_probability':.25,'critical_multiplier':1.3,'samples':expected_samples,'damage':expected})


def case_bpipe_kill_dp():
    data=scene([actor('bpipe',40)],enemies=[(4,5)])
    data['scenarioDraft']['initialEntities'][1]['components']={'resources':{'hp':{'initial':1}}}
    sim=make(data);command(sim,'bpipe','ability/campaign_bpipe_s3');sim.advance(21)
    assert len(events(sim,'combat.kill','bpipe'))==1
    eq(sim.ctx.resources.current('system/battle','dp'),51)
    assert not sim.ctx.alive('enemy0') and len(sim.session.random.samples)==1
    return finish(sim,{'skill_first_hit_kills':True,'kill_dp':1,'corpse_has_no_second_or_third_packet':True})


def case_angel_auto_burst():
    sim=make(scene([actor('angel',30)],enemies=[(4,5)]));sim.advance(19)
    hits=events(sim,'damage.accepted','angel','ability/campaign_angel_burst')
    # Declared model quantizes windup and repeat spacing separately. AS scales
    # first windup; the native spacing field remains .05 =>2 logic ticks.
    first=math.ceil(round(.3/1.12*30,12));spacing=math.ceil(round(.05000000074505806*30,12))
    launch_ticks=[first+i*spacing for i in range(5)]
    assert [e['time'] for e in hits]==[v+1 for v in launch_ticks]
    for e in hits:eq(e['payload']['amount'],607*1.06*1.1-50)
    assert len(events(sim,'attack.accepted','angel','ability/campaign_angel_burst'))==1
    assert len(events(sim,'ability.started','angel','ability/campaign_angel_s3'))==1
    eq(sim.ctx.resources.current('angel','sp'),0)
    return finish(sim,{'auto_skill_cost':30,'packet_count':5,'launch_ticks':launch_ticks,
        'impact_ticks':[t+1 for t in launch_ticks],'damage_per_packet':657.762,'attack_event_count':1})


def case_plosis_three_heals():
    sim=make(scene([actor('plosis',100)],patients=[(4,5),(5,5),(3,5),(4,6)]))
    command(sim,'plosis','ability/plosis_s2_first_packet');sim.advance(31)
    hits=events(sim,'healing.accepted','plosis')
    assert [e['time'] for e in hits]==[7]*3+[30]*3
    assert [e['payload']['amount'] for e in hits]==[382]*6
    assert len({e['payload']['target'] for e in hits})==4
    eq(sim.ctx.resources.current('plosis','sp'),0)
    return finish(sim,{'atk':382,'native_raw_predelay':.20000000298023224,'profile_first_tick':7,
        'interval_seconds':.75,'first_two_packet_groups':[7,30],'three_targets_each':True,'retargets_fourth_injured':True})


def case_eyja_random_targets():
    seed=11;data=scene([actor('amgoat',80)],enemies=[(4,5),(4,6),(5,5)])
    enemy=next(e for e in data['entities'] if e['id']=='unit/deployed_witness_enemy');enemy['components']['attributes']['base']['mres']=50
    sim=make(data,seed);command(sim,'amgoat','ability/campaign_amgoat_s3');sim.advance(11)
    launches=events(sim,'projectile.launched','amgoat')
    expected_samples=samples(seed,3);remaining=[sim.session.world.resolve('enemy'+str(i)) for i in range(3)];selection=[]
    for value in expected_samples:selection.append(remaining.pop(min(len(remaining)-1,math.floor(value*len(remaining)))))
    assert [e['payload']['target'] for e in launches]==selection
    hits=events(sim,'damage.accepted','amgoat','ability/campaign_amgoat_probe_packet')
    assert len(hits)==3
    for e in hits:eq(e['payload']['amount'],710*(1+.14+1.3)*.5)
    assert sorted(e['time'] for e in hits)==[5,8,10]
    for actual,expected in zip(sim.session.random.samples,expected_samples):eq(actual['value'],expected)
    assert len(sim.session.random.samples)==3
    return finish(sim,{'effective_atk':1732.4,'mres':50,'damage_per_target':866.2,'maximum_targets':6,
        'candidate_count':3,'selected_actor_ids':selection,'samples':expected_samples,'impact_ticks':[5,8,10]})


def case_saria_heal_sp():
    data=scene([actor('demkni',80)],patients=[(4,5)])
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/char_010_chen','instanceAlias':'chen',
        'position':{'row':5,'col':4},'components':{'resources':{'hp':{'initial':100},'sp':{'initial':0}}}})
    sim=make(data);command(sim,'demkni','ability/demkni_s3');sim.advance(17)
    positive=[e for e in events(sim,'healing.accepted','demkni') if e['payload']['amount']>0]
    assert len(positive)==2 and [e['time'] for e in positive]==[16,16]
    for e in positive:eq(e['payload']['amount'],513*.35)
    eq(sim.ctx.resources.current('chen','sp'),1)
    return finish(sim,{'first_heal_tick':16,'heal_per_injured_target':179.55,'own_heal_target_sp':1,'no_sp_patient_is_safe':True})


CASES={name[5:]:value for name,value in list(globals().items()) if name.startswith('case_') and callable(value)}


def main():
    global PACKAGE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--runtime-root',type=Path);parser.add_argument('--case',action='append');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();PACKAGE=args.package.resolve()
    if args.runtime_root:sys.path.insert(0,str(args.runtime_root.resolve()))
    import ark_sim
    from ark_sim.adapters.api import implementation_digest
    if args.runtime_root:assert Path(ark_sim.__file__).resolve().is_relative_to(args.runtime_root.resolve())
    selected=args.case or list(CASES);start=implementation_digest();package_sha=sha(PACKAGE);helper_sha=sha(Path(__file__));actual={}
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/operator_sources.lock.json',
        *[ROOT/f'packages/campaign/skills.{name}.json' for name in IDS],
        ROOT/'packages/campaign/talents.attack.json',ROOT/'packages/campaign/talents.support.json']
    source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    result={'schema':'ark-sim/deployed-actor-witnesses/v1','passed':False,'implementation_sha256':start,
        'package':str(PACKAGE),'package_sha256':package_sha,'runtime_module':ark_sim.__file__,
        'selected_cases':selected,'cases':actual,'helper_sha256':helper_sha,
        'source_hashes':source_hashes,
        'fixed_configs':{e['metadata']['native_id']:e['metadata']['config'] for e in read(PACKAGE)['entities']
            if e.get('metadata',{}).get('native_id') in IDS.values()},
        'scope':'explicit six-actor endpoints; no complete actor or stage approval','formal_stage_approved':False}
    for name in selected:
        try:
            actual[name]=CASES[name]();print(json.dumps({'case':name,'passed':True}),flush=True)
        except Exception as error:
            from ark_sim.contracts import thaw
            result['failure']={'case':name,'error':repr(error)}
            if LAST_SIM is not None:
                result['failure']['observed_events']=[thaw(e) for e in LAST_SIM.session.events if e['type'] in
                    ('damage.accepted','healing.accepted','resource.changed','ability.started','projectile.launched','command.rejected')]
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            raise
    assert start==implementation_digest() and package_sha==sha(PACKAGE) and helper_sha==sha(Path(__file__))
    assert source_hashes=={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    result.update(passed=True,identity_stable=True,tests=[{'path':Path(__file__).relative_to(ROOT).as_posix(),
        'source_sha256':helper_sha,'result':'passed','cases':selected}])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


if __name__=='__main__':main()
