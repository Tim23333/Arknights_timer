"""Canonical Chen/Liskarm/Suzuran witnesses; never issues a review receipt."""
from copy import deepcopy
import argparse
import base64
import hashlib
import json
import os
import random
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
PACKAGE=Path(os.environ.get('CAMPAIGN_MECHANISM_PACKAGE',str(ROOT/'packages/campaign/mainline_models/level_main_00-10.m8_roster.json')))
IDS={'chen':'char_010_chen','lisk':'char_107_liskam','lisa':'char_358_lisa','plosis':'char_128_plosis','myrtle':'char_151_myrtle'}


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def actor(name,row=4,col=4,sp=None,hp=None):
    value={'definition':'unit/'+IDS[name],'instanceAlias':name,'position':{'row':row,'col':col},'facing':'right'}
    resources={}
    if sp is not None:resources['sp']={'initial':sp}
    if hp is not None:resources['hp']={'initial':hp}
    if resources:value['components']={'resources':resources}
    return value


def scene(initial,*,enemy=(0,0),target='lisk'):
    data=read(PACKAGE)
    # No canonical definitions or initial talent lists are changed.
    data['scenarioDraft'].update(id='scenario/canonical_trio_witness',map={'rows':9,'cols':12},
        waves=[],scheduledEffects=[],objectives={},initialEntities=deepcopy(initial))
    data['scenarioDraft'].pop('timeline',None)
    for item in data['scenarioDraft']['initialEntities']:
        if item['instanceAlias']==target:
            native=next(e for e in data['entities'] if e['id']==item['definition'])
            item['tags']=list(native['tags'])+['witness_target']
    data['entities'].append({'id':'unit/witness_enemy','kind':'entity','tags':['enemy','ground','witness_enemy'],
        'components':{'attributes':{'base':{'max_hp':1000000,'atk':1000,'def':0,'mres':0,'move_speed':1}},
            'resources':{'hp':{'initial':1000000,'capacity':1000000,'role':'health'}},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'},
            'abilities':['ability/witness_hit_'+k for k in ('physical','arts','true')]+['ability/witness_two_hits','ability/witness_slow']}})
    if enemy is not None:data['scenarioDraft']['initialEntities'].append({'definition':'unit/witness_enemy','instanceAlias':'enemy','position':{'row':enemy[0],'col':enemy[1]}})
    data['selectors'].append({'id':'selector/witness_player','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'witness_target'},{'state':'alive'}],'limit':1})
    for kind in ('physical','arts','true'):
        data['abilities'].append({'id':'ability/witness_hit_'+kind,'kind':'ability','activation':{'mode':'manual'},
            'selector':'selector/witness_player','timeline':[{'at':0,'effect':{'op':'damage','damage_type':kind,'scale':.1}}]})
    data['abilities'].append({'id':'ability/witness_two_hits','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/witness_player','timeline':[{'at':t,'effect':{'op':'damage','damage_type':'true','scale':.1}} for t in (0,1)]})
    data['abilities'].append({'id':'ability/witness_slow','kind':'ability','activation':{'mode':'manual',
        'on_start':[{'op':'apply_buff','target':'source','buff':'buff/support_sluggish'}]},'timeline':[]})
    # A pure source-100 probe packet targets enemy and does not override pipeline.
    data['entities'].append({'id':'unit/witness_probe','kind':'entity','tags':['player'],
        'components':{'attributes':{'base':{'atk':100}},'spatial':{},'abilities':['ability/witness_packet']}})
    data['selectors'].append({'id':'selector/witness_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'witness_enemy'},{'state':'alive'}],'limit':1})
    data['abilities'].append({'id':'ability/witness_packet','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/witness_enemy','timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true'}}]})
    return data


def make(data,seed=11):
    global LAST_SIM
    from ark_sim import Compiler,Engine
    LAST_SIM=Engine.create(Compiler().compile(data),seed=seed)
    return LAST_SIM
def events(sim,kind):return [e for e in sim.session.events if e['type']==kind]
def command(sim,source,ability,at=None):sim.submit({'action':'skill','source':source,'ability':ability},at=at)
def eq(actual,expected):assert abs(actual-expected)<1e-7,(actual,expected)


def finish(sim,*,roundtrip=True):
    from ark_sim import Engine
    from ark_sim.contracts import thaw
    from ark_sim.tools.compare import first_difference
    from ark_sim.tools.replay import replay
    if roundtrip:
        restored=Engine.restore(sim.program,sim.checkpoint())
        sim.advance(2);restored.advance(2)
        assert first_difference(sim.snapshot(),restored.snapshot()) is None
        assert first_difference(sim.snapshot(),replay(sim.program,sim.export_replay()).snapshot()) is None
    return {'program_fingerprint':sim.program.fingerprint,'runtime_fingerprint':sim.runtime_fingerprint,
        'tick':sim.session.time,'checkpoint_equal':roundtrip,'replay_equal':roundtrip,
        'events':[thaw(e) for e in sim.session.events if e['type'] in ('attack.accepted','damage.accepted','regeneration.accepted','ability.started','ability.finished','resource.changed','command.rejected','buff.removed')],
        'random_samples':thaw(sim.session.random.samples),
        'actor_resources':{e.get('definition_id',str(e['id'])):{k:v['current'] for k,v in e['components'].get('resources',{}).items()} for e in sim.session.world.entities()}}


def case_config_sources():
    data=read(PACKAGE);rows={r['character_id']:r for r in read(ROOT/'packages/campaign/operators.normalized.json')['operators']}
    expected={'chen':(2724,628,388,4,0,'skchr_chen_1'),'lisk':(3124,461,731,18,0,'skchr_liskam_1'),'lisa':(1413,576,123,70,50,'skchr_lisa_3')}
    defs={a['id']:a for a in data['abilities']}
    for name,(hp,atk,defense,cost,initial,skill) in expected.items():
        row=rows[IDS[name]];unit=next(e for e in data['entities'] if e['id']=='unit/'+IDS[name]);m=unit['metadata']
        assert m['config']==row['config']
        assert m['config']['elite_phase']==2 and m['config']['level']==70 and m['config']['potential']==1
        assert m['config']['trust_percent']==100 and m['config']['mastery']==3 and m['config']['equipment_id'] is None
        base=unit['components']['attributes']['base'];assert (base['max_hp'],base['atk'],base['def'])==(hp,atk,defense)
        sp=row['selected_skill']['level']['spData'];assert (sp['spCost'],sp['initSp'])==(cost,initial)
        assert defs[m['selected_skill_ability']]['metadata']['native_skill_id']==skill==row['selected_skill']['skill_id']
        assert m['selected_skill_ability'] in unit['components']['abilities']
        assert len(row['talents'])==2
        assert all(t['selected_candidate']['requiredPotentialRank']==0 for t in row['talents'])
        bb={b['key']:b['value'] for b in row['selected_skill']['level']['blackboard']}
        talents=[{b['key']:b['value'] for b in t['selected_candidate']['blackboard']} for t in row['talents']]
        if name=='chen':
            assert sp['spType']=='INCREASE_WHEN_ATTACK' and bb=={'atk_scale':3.2,'stun':1.5}
            assert talents==[{'interval':4.0,'sp':1.0},{'atk':.05,'def':.05,'prob':.1}]
        elif name=='lisk':
            assert sp['spType']=='INCREASE_WHEN_TAKEN_DAMAGE' and sp['increment']==1
            assert bb=={'def':1.0,'duration':8.0} and talents==[{'sp':1.0},{'magic_resistance':10.0}]
        else:
            assert sp['spType']=='INCREASE_WITH_TIME' and row['selected_skill']['level']['duration']==35
            assert bb=={'scale_delta_to_one':2.0,'attack@atk_to_hp_recovery_ratio':.2}
            assert talents==[{'sp_recovery_per_sec':.4},{'damage_scale':1.2,'atk':1.0}]
    return {'fixed_config_checked':3,'source_numerics':'independent constants matched normalized source; no actual-derived expectations'}


def case_chen_attack_once_two_hits():
    sim=make(scene([actor('chen')],enemy=(4,5),target='chen'))
    sim.advance(31)
    attacks=[e for e in events(sim,'attack.accepted') if e['payload']['ability']=='ability/campaign_chen_normal']
    hits=[e for e in events(sim,'damage.accepted') if e['payload']['source']==sim.session.world.resolve('chen')]
    assert len(attacks)==1 and len(hits)==2
    assert [e['time'] for e in hits]==[13,30]
    for hit in hits:eq(hit['payload']['amount'],628*1.05)
    eq(sim.ctx.resources.current('chen','sp'),1)
    return finish(sim)


def case_chen_auto_skill_stun():
    sim=make(scene([actor('chen',sp=4)],enemy=(4,5),target='chen'))
    command(sim,'chen','ability/campaign_chen_s1')
    sim.advance(17)
    assert events(sim,'command.rejected')
    start=[e for e in events(sim,'ability.started') if e['payload']['ability']=='ability/campaign_chen_s1'][0]
    assert start['time']==0
    costs=[e['payload']['delta'] for e in events(sim,'resource.changed') if e['payload'].get('reason')=='ability_cost']
    assert costs==[-4]
    hit=events(sim,'damage.accepted')[0];assert hit['time']==16;eq(hit['payload']['amount'],628*1.05*3.2)
    enemy=sim.session.world.resolve('enemy')
    assert sim.ctx.buffs.controls(enemy)['attack'] is False
    sim.advance(43);assert sim.ctx.buffs.controls(enemy)['attack'] is False
    sim.advance(1);assert sim.ctx.buffs.controls(enemy)['attack'] is True
    return finish(sim)


def case_chen_periodic_source_retire():
    sim=make(scene([actor('chen'),actor('lisk',col=5),actor('lisa',col=6,sp=0)],enemy=None))
    sim.advance(120);eq(sim.ctx.resources.current('chen','sp'),0);eq(sim.ctx.resources.current('lisk','sp'),0)
    sim.advance(1);eq(sim.ctx.resources.current('chen','sp'),1);eq(sim.ctx.resources.current('lisk','sp'),1)
    command_state=sim.ctx.resources.current('lisa','sp');eq(command_state,4*1.4)
    sim.submit({'action':'withdraw','source':'chen'});sim.advance(120)
    eq(sim.ctx.resources.current('lisk','sp'),1)
    return finish(sim)


def case_chen_dodge_and_arts():
    # Independent standard-library implementation of the explicitly declared
    # SHA256/MT model profile; do not derive expected damage from actual samples.
    seed=1;derived=int.from_bytes(hashlib.sha256(json.dumps([seed,'imp'],separators=(',',':')).encode()).digest(),'big')
    expected=random.Random(derived).random();assert expected<.1
    sim=make(scene([actor('chen')],target='chen'),seed=seed)
    command(sim,'enemy','ability/witness_hit_physical');sim.advance(1)
    eq(sim.ctx.resources.current('chen','hp'),2724)
    assert not events(sim,'damage.accepted') and len(sim.session.random.samples)==1
    eq(sim.session.random.samples[0]['value'],expected)
    command(sim,'enemy','ability/witness_hit_arts');sim.advance(1)
    eq(sim.ctx.resources.current('chen','hp'),2624)
    assert len(sim.session.random.samples)==1
    return finish(sim)


def case_lisk_two_source_gains():
    sim=make(scene([actor('lisk')]))
    command(sim,'enemy','ability/witness_two_hits');sim.advance(2)
    eq(sim.ctx.resources.current('lisk','sp'),4)
    assert len(events(sim,'damage.accepted'))==2
    gains=[e for e in events(sim,'resource.changed') if e['payload']['resource']=='sp' and e['payload']['delta']>0]
    assert len(gains)==4 and all(e['payload']['delta']==1 for e in gains)
    assert {e['payload']['source'] for e in gains}=={None,sim.session.world.resolve('lisk')}
    return finish(sim)


def case_lisk_neighbor_empty():
    sim=make(scene([actor('lisk')]))
    command(sim,'enemy','ability/witness_hit_true');sim.advance(1)
    eq(sim.ctx.resources.current('lisk','sp'),2)
    assert len(sim.session.random.samples)==0
    return finish(sim)


def case_lisk_neighbor_random():
    sim=make(scene([actor('lisk'),actor('chen',col=5),actor('lisa',row=5,col=5,sp=0)]))
    command(sim,'enemy','ability/witness_hit_true');sim.advance(1)
    eq(sim.ctx.resources.current('chen','sp'),1)
    eq(sim.ctx.resources.current('lisk','sp'),2)
    eq(sim.ctx.resources.current('lisa','sp'),0)
    assert len(sim.session.random.samples)==1
    return finish(sim)


def case_lisk_two_neighbors():
    seed=1;derived=int.from_bytes(hashlib.sha256(json.dumps([seed,'imp'],separators=(',',':')).encode()).digest(),'big')
    expected=random.Random(derived).random();assert 0<=expected<.5
    sim=make(scene([actor('lisk'),actor('chen',col=5),actor('lisa',col=3,sp=0)]),seed=seed)
    command(sim,'enemy','ability/witness_hit_true');sim.advance(1)
    eq(sim.ctx.resources.current('chen','sp'),1);eq(sim.ctx.resources.current('lisa','sp'),0)
    assert len(sim.session.random.samples)==1;eq(sim.session.random.samples[0]['value'],expected)
    return finish(sim)


def case_lisk_automatic_payment():
    sim=make(scene([actor('lisk')]))
    for tick in range(9):command(sim,'enemy','ability/witness_hit_true',at=tick)
    sim.advance(9);eq(sim.ctx.resources.current('lisk','sp'),18)
    sim.advance(1);eq(sim.ctx.resources.current('lisk','sp'),0);eq(sim.ctx.resources.current('lisk','shield_charge'),1)
    costs=[e for e in events(sim,'resource.changed') if e['payload'].get('reason')=='ability_cost']
    assert len(costs)==1 and costs[0]['payload']['delta']==-18
    return finish(sim)


def case_lisk_shield(kind):
    sim=make(scene([actor('lisk',sp=18)]))
    command(sim,'lisk','ability/liskam_s1')
    command(sim,'enemy','ability/witness_hit_'+kind,at=1)
    sim.advance(2)
    assert events(sim,'command.rejected')
    eq(sim.ctx.resources.current('lisk','hp'),3124)
    eq(sim.ctx.resources.current('lisk','shield_charge'),0)
    assert events(sim,'damage.accepted')[-1]['payload']['amount']==0
    eq(sim.ctx.resources.current('lisk','sp'),0)
    return finish(sim)


def case_lisk_freeze_and_expiry():
    sim=make(scene([actor('lisk',sp=18),actor('chen',col=5)]))
    command(sim,'enemy','ability/witness_hit_true',at=238) # Consume charge, no positive-HP SP.
    command(sim,'enemy','ability/witness_hit_true',at=239)
    sim.advance(240);eq(sim.ctx.resources.current('lisk','sp'),0)
    eq(sim.ctx.resources.current('chen','sp'),2) # Chen own4s talent + one adjacent hit grant.
    sim.advance(1);eq(sim.ctx.resources.current('lisk','shield_charge'),0)
    command(sim,'enemy','ability/witness_hit_true');sim.advance(1)
    eq(sim.ctx.resources.current('lisk','sp'),3) # Chen8s tick240 grants1 then two unfrozen sources.
    return finish(sim)


def case_lisk_blocked_neighbor_profile():
    sim=make(scene([actor('lisk',sp=18),actor('lisa',col=5,sp=0)]))
    command(sim,'enemy','ability/witness_hit_true',at=1)
    sim.advance(2)
    eq(sim.ctx.resources.current('lisk','hp'),3124)
    eq(sim.ctx.resources.current('lisa','sp'),0)
    assert len(sim.session.random.samples)==0
    command(sim,'enemy','ability/witness_hit_true');sim.advance(1)
    eq(sim.ctx.resources.current('lisk','hp'),3024)
    eq(sim.ctx.resources.current('lisk','sp'),0) # Owner manual cast remains frozen.
    eq(sim.ctx.resources.current('lisa','sp'),1)
    assert len(sim.session.random.samples)==1
    return finish(sim)


def case_lisa_highest_sp_retire():
    sim=make(scene([actor('lisa',sp=0),actor('plosis',col=5)],enemy=None,target='lisa'))
    # Periodic resource driver integrates tick0's quantum; 30 quanta first
    # complete at tick29. Buff-trigger timers separately first fire at tick30.
    eq(sim.ctx.resources.current('lisa','sp'),0)
    sim.advance(29);eq(sim.ctx.resources.current('lisa','sp'),0)
    sim.advance(1);eq(sim.ctx.resources.current('lisa','sp'),1.4)
    sim.submit({'action':'withdraw','source':'lisa'})
    before=sim.ctx.resources.current('plosis','sp');sim.advance(30)
    eq(sim.ctx.resources.current('plosis','sp')-before,1.3)
    return finish(sim)


def lisa_scene(sp=70,hp=None):
    data=scene([actor('lisa',sp=sp,hp=hp)],enemy=(4,5),target='lisa')
    data['scenarioDraft']['initialEntities'].append({'definition':'unit/witness_probe','instanceAlias':'probe','position':{'row':0,'col':1}})
    return data


def case_lisa_fragility_and_retire():
    sim=make(lisa_scene(sp=0));command(sim,'probe','ability/witness_packet');sim.advance(1)
    probe=sim.session.world.resolve('probe')
    hits=[e for e in events(sim,'damage.accepted') if e['payload']['source']==probe];eq(hits[-1]['payload']['amount'],100)
    command(sim,'enemy','ability/witness_slow');command(sim,'probe','ability/witness_packet');sim.advance(1)
    hits=[e for e in events(sim,'damage.accepted') if e['payload']['source']==probe];eq(hits[-1]['payload']['amount'],120)
    sim.submit({'action':'withdraw','source':'lisa'});sim.advance(1)
    command(sim,'probe','ability/witness_packet');sim.advance(1)
    hits=[e for e in events(sim,'damage.accepted') if e['payload']['source']==probe];eq(hits[-1]['payload']['amount'],100)
    return finish(sim)


def case_lisa_s3_regeneration_freeze():
    sim=make(lisa_scene(hp=500));command(sim,'lisa','ability/lisa_s3');command(sim,'probe','ability/witness_packet')
    sim.advance(30);eq(sim.ctx.resources.current('lisa','hp'),500)
    sim.advance(1);eq(sim.ctx.resources.current('lisa','hp'),500+576*.2)
    eq(sim.ctx.resources.current('lisa','sp'),0)
    assert not events(sim,'healing.accepted') and len(events(sim,'regeneration.accepted'))==1
    eq([e for e in events(sim,'damage.accepted') if e['payload']['source']==sim.session.world.resolve('probe')][0]['payload']['amount'],140)
    assert not [e for e in events(sim,'attack.accepted') if e['payload']['source']==sim.session.world.resolve('lisa')]
    return finish(sim)


def case_lisa_half_open():
    sim=make(lisa_scene());command(sim,'lisa','ability/lisa_s3');command(sim,'probe','ability/witness_packet',at=1049);command(sim,'probe','ability/witness_packet',at=1050)
    sim.advance(1051)
    probe=sim.session.world.resolve('probe');hits=[e for e in events(sim,'damage.accepted') if e['payload']['source']==probe]
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(1049,140),(1050,100)]
    # Regeneration preserves accepted zero-amount packets at capacity; its
    # half-open timer runs30..1020, never1050. It is distinct from ordinary heal.
    pulses=events(sim,'regeneration.accepted')
    assert [(e['time'],e['payload']['amount']) for e in pulses]==[(t,0) for t in range(30,1050,30)]
    assert sim.ctx.buffs.controls('lisa')['attack'] is True
    return finish(sim)


def case_lisa_live_member_exit():
    data=lisa_scene()
    enemy=next(e for e in data['entities'] if e['id']=='unit/witness_enemy')
    for name,pos in [('out',{'row':0,'col':0}),('in',{'row':4,'col':5})]:
        aid='ability/witness_move_'+name;enemy['components']['abilities'].append(aid)
        data['abilities'].append({'id':aid,'kind':'ability','activation':{'mode':'manual'},
            'timeline':[{'at':0,'effect':{'op':'move','target':'source','position':pos}}]})
    sim=make(data);command(sim,'lisa','ability/lisa_s3');sim.advance(1)
    for mode in ('out','in'):
        command(sim,'enemy','ability/witness_move_'+mode);sim.advance(1)
        command(sim,'probe','ability/witness_packet');sim.advance(1)
    probe=sim.session.world.resolve('probe')
    hits=[e for e in events(sim,'damage.accepted') if e['payload']['source']==probe]
    assert [e['payload']['amount'] for e in hits]==[100,140]
    return finish(sim)


CASES={'config_sources':case_config_sources,'chen_attack_once_two_hits':case_chen_attack_once_two_hits,
    'chen_auto_skill_stun':case_chen_auto_skill_stun,'chen_periodic_source_retire':case_chen_periodic_source_retire,
    'chen_dodge_and_arts':case_chen_dodge_and_arts,
    'lisk_two_source_gains':case_lisk_two_source_gains,'lisk_neighbor_empty':case_lisk_neighbor_empty,
    'lisk_neighbor_random':case_lisk_neighbor_random,'lisk_automatic_payment':case_lisk_automatic_payment,
    'lisk_two_neighbors':case_lisk_two_neighbors,
    **{'lisk_shield_'+k:(lambda kind=k:case_lisk_shield(kind)) for k in ('physical','arts','true')},
    'lisk_freeze_and_expiry':case_lisk_freeze_and_expiry,'lisa_highest_sp_retire':case_lisa_highest_sp_retire,
    'lisk_blocked_neighbor_profile':case_lisk_blocked_neighbor_profile,
    'lisa_fragility_and_retire':case_lisa_fragility_and_retire,'lisa_s3_regeneration_freeze':case_lisa_s3_regeneration_freeze,
    'lisa_half_open':case_lisa_half_open,'lisa_live_member_exit':case_lisa_live_member_exit}


LAST_SIM=None
def run_case(name):
    global LAST_SIM
    LAST_SIM=None
    try:
        value={'case':name,'result':'passed','actual':CASES[name]()}
    except Exception as error:
        value={'case':name,'result':'failed','error':repr(error)}
        if LAST_SIM is not None:value['actual']=finish(LAST_SIM,roundtrip=False)
        output=os.environ.get('CAMPAIGN_CASE_RESULTS')
        if output:
            with open(output,'a',encoding='utf8') as stream:stream.write(json.dumps(value)+'\n')
        raise
    output=os.environ.get('CAMPAIGN_CASE_RESULTS')
    if output:
        with open(output,'a',encoding='utf8') as stream:stream.write(json.dumps(value)+'\n')
    return value


def source_witness():
    from tools.build_kalts_skill_recipe import decode_bson_document
    from tools.extract_campaign_animation_bindings import unity_payload
    path=ROOT.parent/'data/anon_textassets/buff_template_data.dat';payload=unity_payload(path.read_bytes());values,spans=decode_bson_document(payload)
    lo,hi=spans[('damage_block_once',)];raw=payload[lo:hi]
    actions=values['damage_block_once']['eventToActions']['ON_TAKE_DAMAGE']
    assert [a['$type'].split('+')[1].split(',')[0] for a in actions]==['BlockDamage','FinishBuff']
    assert actions[0]['_filterDamageType'] is False and actions[0]['_filterApplyWay'] is False
    return {'path':str(path),'file_sha256':sha(path),'template':'damage_block_once','bson_offset':lo,
        'bson_document_sha256':hashlib.sha256(raw).hexdigest(),'bson_document_base64':base64.b64encode(raw).decode(),
        'parsed':values['damage_block_once'],'native_packet_SP_order_method_body_verified':False,
        'SP_profile':'source defense spType increment1 plus independent talent self1; accepted-packet model; blocked-hit native order client_pending'}


def main():
    global PACKAGE
    from ark_sim.adapters.api import implementation_digest
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'validation/campaign/canonical_trio_witness.m8_damage.json')
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--case',action='append',choices=list(CASES),help='Export only these independently executed cases')
    args=parser.parse_args()
    PACKAGE=args.package.resolve()
    test=ROOT/'tests_v2/test_canonical_roster_trio.py'
    selected=args.case or list(CASES)
    sources=[ROOT/'packages/campaign/operators.normalized.json',ROOT/'packages/campaign/skills.chen.json',ROOT/'packages/campaign/skills.liskam.json',ROOT/'packages/campaign/skills.lisa.json',ROOT/'packages/campaign/talents.attack.json',ROOT/'packages/campaign/talents.support.json',ROOT/'packages/campaign/roster.reference.json',ROOT/'packages/campaign/animation_bindings.reference.json',ROOT/'packages/campaign/attacks.reference.json',ROOT.parent/'data/anon_textassets/buff_template_data.dat']
    identity_paths=[PACKAGE,test,Path(__file__),ROOT/'tools/build_kalts_skill_recipe.py',ROOT/'tools/extract_campaign_animation_bindings.py',*sources]
    start_identity={'implementation_sha256':implementation_digest(),'files':{str(p.resolve()):sha(p) for p in identity_paths}}
    with tempfile.TemporaryDirectory(prefix='ark_trio_') as directory:
        path=Path(directory)/'results.jsonl'
        env=dict(os.environ,CAMPAIGN_CASE_RESULTS=str(path),CAMPAIGN_MECHANISM_PACKAGE=str(PACKAGE))
        nodes=[str(test)+'::test_canonical_mechanism['+name+']' for name in selected]
        run=subprocess.run([sys.executable,'-m','pytest',*nodes,'-q','--tb=short'],cwd=ROOT,capture_output=True,text=True,env=env)
        results=[json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
    raw_source=source_witness()
    end_identity={'implementation_sha256':implementation_digest(),'files':{str(p.resolve()):sha(p) for p in identity_paths}}
    stable=start_identity==end_identity
    passed=stable and run.returncode==0 and len(results)==len(selected) and all(r['result']=='passed' for r in results)
    evidence={'schema':'ark-sim/campaign-mechanism-test-evidence/v1','passed':passed,
        'implementation_sha256':implementation_digest(),'tests':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(p),'result':'passed' if passed else 'failed'} for p in (test,Path(__file__))],
        'helper_source_sha256':sha(Path(__file__)),'input_package':str(PACKAGE),'input_package_sha256':sha(PACKAGE),
        'source_hashes':{str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p).replace('\\','/'):sha(p) for p in sources},
        'identity_stable':stable,'identity_at_start':start_identity,'identity_at_completion':end_identity,
        'fixed_configs':{r['character_id']:r['config'] for r in read(sources[0])['operators'] if r['character_id'] in list(IDS.values())[:3]},
        'pytest_exit_code':run.returncode,'pytest_output':run.stdout+run.stderr,'selected_cases':selected,'cases':results,'shield_source_witness':raw_source,
        'scope':'three canonical mechanisms only; no full stage or roster acceptance','formal_approval':False,'review_receipt':False,
        'client_pending_preserved':True}
    args.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':passed,'cases':len(results),'failed':[r['case'] for r in results if r['result']=='failed'],'output':str(args.output)}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
