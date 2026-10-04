"""Actual damage/resource/aura/RNG witnesses, distinct from client calibration."""
from copy import deepcopy
import base64
import hashlib

import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from tools.build_campaign_attack_talents import OUTPUT,read,build,IDS


@pytest.fixture(scope='module')
def package():return read(OUTPUT)


def scene(package,initial,roster=()):
    data=deepcopy(package)
    # This talent-isolation scene suppresses unrelated base attacks and SP caps;
    # actual package retains native normalized stats and selected SP endpoints.
    for e in data['entities']:
        e['components']['abilities']=[k for k in e['components']['abilities'] if '/normal_attack' not in k]
        e['components']['resources']['sp']={'initial':0,'capacity':100}
    data['entities'].append({'id':'unit/target','kind':'entity','tags':['enemy','ground'],
        'components':{'attributes':{'base':{'max_hp':100000,'atk':100,'def':0,'mres':0}},
            'resources':{'hp':{'initial':100000,'capacity':100000,'role':'health'}},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    data['scenarioDraft']={'id':'scenario/attack_talents','ruleset':'ruleset/ark_standard',
        'map':{'rows':7,'cols':12},'resources':{'dp':{'initial':0,'capacity':99}},
        'roster':list(roster),'initialEntities':initial,'dependencies':['unit/'+cid for cid in IDS]}
    return data


def actor(cid,alias,row=3,col=3,**components):
    return {'definition':'unit/'+cid,'instanceAlias':alias,'position':{'row':row,'col':col},
        'components':components}


def make(data,seed=11):return Engine.create(Compiler().compile(data),seed=seed)
def events(s,kind):return [e for e in s.session.events if e['type']==kind]
def damage(s,source,target,kind='physical',scale=1):
    s.ctx.effects.execute(source,[s.session.world.resolve(target)],{'op':'damage','damage_type':kind,'scale':scale})


def test_build_exact_sources_selected_rank_and_strict_bson(package):
    assert build()==package
    source=package['manifest']['metadata']['source']
    assert len(source['operators'])==6
    assert all(t['selected_candidate']['requiredPotentialRank']==0 for r in source['operators'].values() for t in r['normalized']['talents'])
    for t in source['bson']['templates'].values():
        assert hashlib.sha256(base64.b64decode(t['bson_document_base64'])).hexdigest()==t['bson_document_sha256']
    dice=source['bson']['templates']['bpipe_t_1']['parsed']['eventToActions']['ON_CALCULATE_DAMAGE']
    assert [a['$type'].split('+')[1].split(',')[0] for a in dice]==['IsBlackboardZero','Dice','AtkScaleUp','SplashDamage']
    assert source['bson']['templates']['amgoat_t_2']['parsed']['eventToActions']['ON_OWNER_LOCATE'][0]['_convertToInt'] is False
    with pytest.raises(ValueError,match='unsupported'):build(require_complete=True)


def test_actual_passive_stats_and_rank_excludes_upgraded_values(package):
    sim=make(scene(package,[actor(IDS[2],'chen'),actor(IDS[3],'lisk',col=4),actor(IDS[4],'angel',col=5)]))
    assert sim.ctx.attributes.value('chen','atk')==pytest.approx(628*1.05)
    assert sim.ctx.attributes.value('chen','def')==pytest.approx(388*1.05)
    assert sim.ctx.attributes.value('lisk','mres')==10
    assert sim.ctx.attributes.value('angel','attack_speed_ratio')==1.12
    assert sim.ctx.attributes.value('angel','atk')==pytest.approx(607*1.06)
    assert sim.ctx.attributes.value('angel','max_hp')==pytest.approx(1598*1.1)


def test_myrtle_regeneration_applies_only_living_vanguard_and_stops_on_alias_retire(package):
    sim=make(scene(package,[actor(IDS[0],'myrtle',resources={'hp':{'initial':100}}),
        actor(IDS[1],'bpipe',col=4,resources={'hp':{'initial':100}}),
        actor(IDS[3],'lisk',col=5,resources={'hp':{'initial':100}})]))
    sim.advance(31)
    assert sim.ctx.resources.current('myrtle','hp')==pytest.approx(125)
    assert sim.ctx.resources.current('bpipe','hp')==pytest.approx(125)
    assert sim.ctx.resources.current('lisk','hp')==100
    sim.ctx.lifecycle.retire('myrtle','withdrawn');sim.advance(31)
    assert sim.ctx.resources.current('bpipe','hp')==pytest.approx(125)


def test_eyja_caster_aura_includes_self_and_cleanup_is_immediate(package):
    data=scene(package,[actor(IDS[5],'eyja'),actor(IDS[4],'angel',col=4)])
    sim=make(data)
    assert sim.ctx.attributes.value('eyja','atk')==pytest.approx(710*1.14)
    assert sim.ctx.attributes.value('angel','atk')==pytest.approx(607*1.06)
    sim.ctx.lifecycle.retire('eyja','withdrawn')
    assert not sim.ctx.get('eyja',('buffs','instances')) or not sim.ctx.alive('eyja')


def test_bpipe_deck_initial_sp_applies_without_source_live_and_not_if_absent(package):
    data=scene(package,[actor(IDS[0],'myrtle'),actor(IDS[3],'lisk',col=4)],['unit/'+IDS[1]])
    sim=make(data)
    assert sim.ctx.resources.current('myrtle','sp')==6
    assert sim.ctx.resources.current('lisk','sp')==0
    assert not any(e['definition_id']=='unit/'+IDS[1] for e in sim.session.world.entities())
    sim.ctx.lifecycle.create('unit/'+IDS[0],position={'row':1,'col':1},alias='second')
    assert sim.ctx.resources.current('second','sp')==6
    data['scenarioDraft']['roster']=[];sim=make(data)
    assert sim.ctx.resources.current('myrtle','sp')==0


def test_chen_four_second_first_wait_and_sp_type_filter(package):
    sim=make(scene(package,[actor(IDS[2],'chen'),actor(IDS[3],'lisk',col=4),actor(IDS[0],'myrtle',col=5)]))
    sim.advance(120)
    assert sim.ctx.resources.current('chen','sp')==0
    sim.advance(1)
    assert sim.ctx.resources.current('chen','sp')==1
    assert sim.ctx.resources.current('lisk','sp')==1
    assert sim.ctx.resources.current('myrtle','sp')==0


def test_liskam_hit_self_and_exact_adjacent_random_friend_no_diagonal(package):
    initial=[actor(IDS[3],'lisk'),actor(IDS[0],'near',col=4),actor(IDS[0],'diagonal',row=4,col=4),
        {'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':5}}]
    sim=make(scene(package,initial));damage(sim,'attacker','lisk');sim.advance(1)
    assert sim.ctx.resources.current('lisk','sp')==1
    assert sim.ctx.resources.current('near','sp')==1
    assert sim.ctx.resources.current('diagonal','sp')==0
    assert len(sim.session.random.samples)==1


def test_liskam_empty_friend_still_self_sp_without_selector_draw(package):
    sim=make(scene(package,[actor(IDS[3],'lisk'),{'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':5}}]))
    damage(sim,'attacker','lisk');sim.advance(1)
    assert sim.ctx.resources.current('lisk','sp')==1
    assert len(sim.session.random.samples)==0


def test_eyja_uniform_float_deploy_sp_consumes_actual_sample(package):
    sim=make(scene(package,[]))
    ref=sim.ctx.lifecycle.create('unit/'+IDS[5],position={'row':3,'col':3},alias='eyja',deployed=True)
    sim.advance(1)
    sample=sim.session.random.samples[0]['value']
    assert sim.ctx.resources.current(ref,'sp')==pytest.approx(7+9*sample)
    assert 7 <= sim.ctx.resources.current(ref,'sp') < 16
    assert len(sim.session.random.samples)==1


def test_angel_deploy_selects_one_friend_keeps_self_and_no_candidate_no_draw(package):
    sim=make(scene(package,[actor(IDS[0],'one'),actor(IDS[3],'two',col=4)]))
    sim.ctx.lifecycle.create('unit/'+IDS[4],position={'row':2,'col':2},alias='angel',deployed=True);sim.advance(1)
    assert sim.ctx.attributes.value('angel','atk')==pytest.approx(607*1.06)
    blessed=sum(sim.ctx.attributes.value(alias,'atk')>base for alias,base in [('one',520),('two',461)])
    assert blessed==1 and len(sim.session.random.samples)==1
    sim=make(scene(package,[]));sim.ctx.lifecycle.create('unit/'+IDS[4],position={'row':2,'col':2},deployed=True);sim.advance(1)
    assert len(sim.session.random.samples)==0


def test_bpipe_actual_packet_proc_scales_primary_splashes_one_and_locks_recursion(package):
    data=scene(package,[actor(IDS[1],'bpipe'),{'definition':'unit/target','instanceAlias':'first','position':{'row':3,'col':4}},
        {'definition':'unit/target','instanceAlias':'second','position':{'row':3,'col':3}},
        {'definition':'unit/target','instanceAlias':'outside','position':{'row':3,'col':8}}])
    sim=make(data)
    for _ in range(20):damage(sim,'bpipe','first')
    samples=[r['value'] for r in sim.session.random.samples];procs=sum(v<.25 for v in samples)
    assert len(samples)==20 and procs>0
    hits=events(sim,'damage.accepted')
    primary=[e['payload']['amount'] for e in hits if e['payload']['target']==sim.session.world.resolve('first')]
    assert primary==pytest.approx([845 if v<.25 else 650 for v in samples])
    assert sum(e['payload']['amount'] for e in hits if e['payload']['target']==sim.session.world.resolve('second'))==pytest.approx(845*procs)
    assert sim.ctx.resources.current('outside','hp')==100000


def test_bpipe_kill_dp_has_real_killer_attribution_and_no_repeat_on_corpse(package):
    data=scene(package,[actor(IDS[1],'bpipe'),actor(IDS[0],'myrtle',col=5),
        {'definition':'unit/target','instanceAlias':'first','position':{'row':3,'col':4},'components':{'resources':{'hp':{'initial':1}}}}])
    sim=make(data);damage(sim,'bpipe','first');sim.advance(1)
    assert sim.ctx.resources.current('system/battle','dp')==1
    damage(sim,'myrtle','first');sim.advance(1)
    assert sim.ctx.resources.current('system/battle','dp')==1


def test_chen_physical_dodge_draws_per_packet_and_arts_never_consumes_dodge_rng(package):
    sim=make(scene(package,[actor(IDS[2],'chen'),{'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':4}}]))
    for _ in range(30):damage(sim,'attacker','chen')
    samples=[r['value'] for r in sim.session.random.samples]
    assert len(samples)==30
    assert len(events(sim,'damage.rejected'))==sum(v<.1 for v in samples)
    before=len(samples);damage(sim,'attacker','chen','arts')
    assert len(sim.session.random.samples)==before


def test_eyja_skill_animations_have_no_attack_events_in_either_native_face(package):
    animation=package['manifest']['metadata']['source']['eyja_animation']
    for asset in animation['assets'].values():
        for name in ('Skill_Start','Skill_Loop','Skill_End'):
            if name in asset['parsed']['animations']:
                assert asset['parsed']['animations'][name]['events']==[]
    assert any('Skill_Loop' not in a['parsed']['animations'] for a in animation['assets'].values())
    assert 'eyja_s3_native_signal_offset_unresolved' in package['manifest']['metadata']['pending']


def test_random_damage_deck_restore_and_replay_are_exact(package):
    data=scene(package,[actor(IDS[1],'bpipe'),{'definition':'unit/target','instanceAlias':'first','position':{'row':3,'col':4}}],['unit/'+IDS[1]])
    a={'id':'ability/test_packet','kind':'ability','activation':{'mode':'manual'},'selector':'selector/test',
        'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'physical'}}]}
    data['abilities'].append(a);data['entities'][1]['components']['abilities'].append(a['id'])
    data['selectors'].append({'id':'selector/test','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
    program=Compiler().compile(data);sim=Engine.create(program,seed=11)
    for at in (1,4,7):sim.submit({'action':'skill','source':'bpipe','ability':a['id']},at=at)
    sim.advance(3);restored=Engine.restore(program,sim.checkpoint());sim.advance(7);restored.advance(7)
    assert first_difference(sim.snapshot(),restored.snapshot()) is None
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None


@pytest.mark.parametrize('field,value',[('trust_percent',0),('potential_rank',4),('potential',6),
    ('equipment_id','unreviewed_module'),('mastery',2)])
def test_selected_source_configuration_drift_fails_instead_of_guess(monkeypatch,field,value):
    import tools.build_campaign_attack_talents as tool
    original=tool.read
    def altered(path):
        data=original(path)
        if path==tool.NORMALIZED:
            row=next(r for r in data['operators'] if r['character_id']==IDS[0])
            row['config'][field]=value
        return data
    monkeypatch.setattr(tool,'read',altered)
    with pytest.raises(ValueError,match='configuration changed|require E270'):tool.source()


def test_chen_external_sp_and_lisk_hit_grants_respect_active_manual_freeze(package):
    data=scene(package,[actor(IDS[2],'chen'),actor(IDS[3],'lisk',col=4),actor(IDS[0],'friend',col=5),
        {'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':6}}])
    busy={'id':'ability/test_busy','kind':'ability','activation':{'mode':'manual'},'duration_seconds':4.1,'timeline':[]}
    data['abilities'].append(busy)
    for e in data['entities']:
        if e['id'] in ('unit/'+IDS[3],'unit/'+IDS[0]):
            e['components']['abilities'].append(busy['id'])
            e['components']['resources']['sp']['parameters']={'freeze_while_cast':True,'freeze_cast_modes':['manual']}
    sim=make(data);sim.ctx.abilities.start('lisk',busy['id']);sim.ctx.abilities.start('friend',busy['id'])
    damage(sim,'attacker','lisk');sim.advance(121)
    assert sim.ctx.resources.current('lisk','sp')==0
    assert sim.ctx.resources.current('friend','sp')==0
    assert sim.ctx.resources.current('chen','sp')==1
    assert len(events(sim,'resource.recovery_suppressed'))>=3


def test_lisk_zero_damage_accepted_packet_still_grants_self_and_dead_friend_is_excluded(package):
    data=scene(package,[actor(IDS[3],'lisk'),actor(IDS[0],'friend',col=4),
        {'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':6}}])
    data['rules'].append({'id':'rule/accepted_zero','kind':'calculation_rule','contract':'damage.pipeline',
        'implementation':{'type':'graph','nodes':[{'id':'result','expression':"{'accepted':True,'amount':0,'allocations':[],'events':[]}"}], 'output':'nodes.result'}})
    data['buffs'].append({'id':'buff/test_zero','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/accepted_zero'}]})
    data['entities'][3]['components']['buffs']['initial'].append('buff/test_zero')
    sim=make(data);sim.ctx.lifecycle.retire('friend','withdrawn');damage(sim,'attacker','lisk');sim.advance(1)
    assert sim.ctx.resources.current('lisk','sp')==1
    assert len(sim.session.random.samples)==0
    assert events(sim,'damage.accepted')[0]['payload']['amount']==0


def test_random_sp_failure_rolls_back_rng_resources_and_public_events(package):
    data=scene(package,[actor(IDS[5],'eyja')])
    sim=make(data);before=deepcopy(sim.snapshot());log=deepcopy(sim.session.events)
    with pytest.raises(ValueError,match='absent'):
        sim.ctx.effects.execute('eyja',[sim.session.world.resolve('eyja')],
            {'op':'random','stream':'imp','probability':1,'on_success':[
                {'op':'modify_resource','resource':'absent','amount_rule':'rule/talent_eyja_random_sp'}]})
    assert sim.snapshot()==before and sim.session.events==log
    assert len(sim.session.random.samples)==0


def test_eyja_automatic_profile_live_dynamic_targets_and_exact_model_interval(package):
    targets=[{'definition':'unit/target','instanceAlias':f'enemy{i}','position':{'row':3,'col':4}} for i in range(3)]
    data=scene(package,[actor(IDS[5],'eyja')]+targets)
    # Source native cost/initial-SP are restored after the scene's isolated cap.
    next(e for e in data['entities'] if e['id']=='unit/'+IDS[5])['components']['resources']['sp'].update(initial=80)
    sim=make(data)
    sim.submit({'action':'skill','source':'eyja','ability':'ability/campaign_amgoat_s3'})
    sim.advance(46)
    starts=[e['time'] for e in events(sim,'ability.started') if e['payload']['ability']=='ability/campaign_amgoat_probe_packet']
    assert starts==[0,15,30,45]
    assert len(sim.session.random.samples)==12
    assert sim.ctx.attributes.value('eyja','max_targets')==6
    first=[e['payload']['amount'] for e in events(sim,'damage.accepted') if e['time']==5]
    assert first==pytest.approx([1732.4]*3)
    assert sim.ctx.resources.current('eyja','sp')==0
    sim.ctx.lifecycle.retire('enemy0','withdrawn');sim.advance(15)
    assert len(sim.session.random.samples)==14
    sim.submit({'action':'skill','source':'eyja','ability':'ability/campaign_amgoat_probe_packet'})
    sim.advance(1)
    assert events(sim,'command.rejected')
    assert package['manifest']['metadata']['model_profiles']['eyja_s3']['client_calibrated'] is False


def test_eyja_midcycle_restart_cancels_not_yet_launched_normal_packet(package):
    data=scene(package,[actor(IDS[5],'eyja'),{'definition':'unit/target','instanceAlias':'enemy','position':{'row':3,'col':4}}])
    e=next(e for e in data['entities'] if e['id']=='unit/'+IDS[5])
    e['components']['abilities'].append('ability/'+IDS[5]+'/normal_attack')
    e['components']['resources']['sp'].update(initial=80)
    sim=make(data);sim.advance(10)
    sim.submit({'action':'skill','source':'eyja','ability':'ability/campaign_amgoat_s3'});sim.advance(21)
    starts=[e['time'] for e in events(sim,'ability.started') if e['payload']['ability']=='ability/campaign_amgoat_probe_packet']
    assert starts==[10,25]
    assert not any(e['payload']['ability']=='ability/'+IDS[5]+'/normal_attack' for e in events(sim,'damage.accepted'))


def test_eyja_restart_preserves_already_launched_normal_projectile(package):
    data=scene(package,[actor(IDS[5],'eyja'),{'definition':'unit/target','instanceAlias':'enemy','position':{'row':3,'col':4}}])
    e=next(e for e in data['entities'] if e['id']=='unit/'+IDS[5]);e['components']['resources']['sp'].update(initial=80)
    e['components']['abilities'].append('ability/'+IDS[5]+'/normal_attack')
    sim=make(data);sim.advance(21)
    sim.submit({'action':'skill','source':'eyja','ability':'ability/campaign_amgoat_s3'});sim.advance(10)
    assert any(e['time']==23 and e['payload']['ability']=='ability/'+IDS[5]+'/normal_attack' for e in events(sim,'damage.accepted'))
    assert any(e['time']==21 and e['payload']['ability']=='ability/campaign_amgoat_probe_packet' for e in events(sim,'ability.started'))


def test_attack_windup_divisor_caps_are_explicit_model_not_native_accuracy(package):
    data=scene(package,[actor(IDS[4],'angel')])
    rid='rule/talent_clock/'+IDS[4]+'/0'
    data['scenarioDraft']['dependencies'].append(rid);sim=make(data)
    assert sim.ctx.calc('ability.windup',{'attributes':{'attack_speed_ratio':1.12},'animation':{},
        'timing_parameters':{'seconds':.3}},rule_id=rid)==pytest.approx(.3/1.12)
    assert sim.ctx.calc('ability.windup',{'attributes':{'attack_speed_ratio':3},'animation':{},
        'timing_parameters':{'seconds':.3}},rule_id=rid)==.15
    profile=package['manifest']['metadata']['model_profiles']['attack_windup']
    assert profile['client_formula_verified'] is False


def test_bpipe_withdraw_refunds_actual_payment_but_caps_at_native_raw_cost(package):
    data=scene(package,[],['unit/'+IDS[1]])
    data['scenarioDraft']['resources']['dp']['initial']=90
    data['rules'].append({'id':'rule/test_cost20','kind':'calculation_rule','contract':'deploy.cost',
        'implementation':{'type':'expression','expression':'20'}})
    e=next(e for e in data['entities'] if e['id']=='unit/'+IDS[1])
    e['components']['deployable']['rules']={'deploy.cost':'rule/test_cost20'}
    sim=make(data)
    sim.submit({'action':'deploy','entity':e['id'],'alias':'bpipe','position':{'row':3,'col':3}});sim.advance(1)
    assert sim.ctx.resources.current('system/battle','dp')==70
    assert sim.ctx.get('bpipe',('deployable','paid_cost'))==20
    sim.submit({'action':'withdraw','source':'bpipe'});sim.advance(1)
    assert sim.ctx.resources.current('system/battle','dp')==83
    assert not sim.ctx.alive('bpipe')


def test_multihit_and_proc_splash_keep_attack_sp_once_per_cast(package):
    data=scene(package,[actor(IDS[1],'bpipe'),
        {'definition':'unit/target','instanceAlias':'first','position':{'row':3,'col':4}},
        {'definition':'unit/target','instanceAlias':'second','position':{'row':3,'col':3}}])
    data['selectors'].append({'id':'selector/test_primary','kind':'selector',
        'region':{'type':'grid_offsets','offsets':[[0,1]]},'filters':[{'tag':'enemy'}],'limit':1})
    a={'id':'ability/test_threehit','kind':'ability','activation':{'mode':'manual',
        'parameters':{'counts_as_attack':True,'sp_resource':'sp','recovery_per_attack':1}},
        'selector':'selector/test_primary','timeline':[{'at':0,'repeat':{'count':3,'interval_seconds':.1},
            'effect':{'op':'damage','damage_type':'physical'}}]}
    data['abilities'].append(a);next(e for e in data['entities'] if e['id']=='unit/'+IDS[1])['components']['abilities'].append(a['id'])
    sim=make(data);sim.submit({'action':'skill','source':'bpipe','ability':a['id']});sim.advance(8)
    assert len(sim.session.random.samples)==3
    assert sim.ctx.resources.current('bpipe','sp')==1
    assert len(events(sim,'attack.accepted'))==1


def test_liskam_random_nonsp_friend_does_not_rollback_hit_or_create_fake_sp(package):
    data=scene(package,[actor(IDS[3],'lisk'),
        {'definition':'unit/nosp_friend','instanceAlias':'device','position':{'row':3,'col':4}},
        {'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':5}}])
    data['entities'].append({'id':'unit/nosp_friend','kind':'entity','tags':['player','ground'],
        'components':{'spatial':{},'attributes':{'base':{'max_hp':100}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}}}})
    sim=make(data);before=sim.ctx.resources.current('lisk','hp');damage(sim,'attacker','lisk');sim.advance(1)
    assert sim.ctx.resources.current('lisk','hp')==before-5
    assert sim.ctx.resources.current('lisk','sp')==1
    assert 'sp' not in sim.ctx.get('device',('resources',))
    assert len(sim.session.random.samples)==1


def test_lisk_emission_time_freeze_survives_self_and_friend_finishing_same_tick(package):
    data=scene(package,[actor(IDS[3],'lisk'),actor(IDS[0],'friend',col=4),
        {'definition':'unit/target','instanceAlias':'attacker','position':{'row':3,'col':5}}])
    receive={'id':'ability/test_receive','kind':'ability','activation':{'mode':'manual'},
        'selector':'selector/test_lisk','timeline':[{'at':1,'effect':{'op':'damage','damage_type':'physical'}}]}
    hold={'id':'ability/test_one_tick_hold','kind':'ability','activation':{'mode':'manual'},
        'duration_seconds':1/30,'timeline':[]}
    data['abilities'] += [receive,hold]
    data['selectors'].append({'id':'selector/test_lisk','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'profession:TANK'}],'limit':1})
    data['entities'][-1]['components']['abilities']=[receive['id']]
    for entity in data['entities']:
        if entity['id'] in ('unit/'+IDS[3],'unit/'+IDS[0]):
            entity['components']['abilities'].append(hold['id'])
            entity['components']['resources']['sp']['parameters']={'freeze_while_cast':True,'freeze_cast_modes':['manual']}
    sim=make(data)
    # Damage precedes both finishes; queued Buff reaction follows them. The
    # eligibility belongs to emission, not the later reaction's live state.
    sim.ctx.abilities.start('attacker',receive['id'])
    sim.ctx.abilities.start('lisk',hold['id']);sim.ctx.abilities.start('friend',hold['id'])
    sim.advance(2)
    assert len(events(sim,'damage.accepted'))==1
    assert sim.ctx.resources.current('lisk','sp')==0
    assert sim.ctx.resources.current('friend','sp')==0
    assert len(events(sim,'resource.recovery_suppressed'))==2
    assert len(sim.session.random.samples)==1


@pytest.mark.parametrize('negative',[False,True])
def test_dynamic_amount_rule_honors_freeze_for_positive_gain_but_not_negative_change(package,negative):
    data=scene(package,[actor(IDS[5],'eyja')])
    busy={'id':'ability/test_dynamic_busy','kind':'ability','activation':{'mode':'manual'},'duration_seconds':1,'timeline':[]}
    data['abilities'].append(busy)
    entity=next(e for e in data['entities'] if e['id']=='unit/'+IDS[5])
    entity['components']['abilities'].append(busy['id'])
    entity['components']['resources']['sp'].update(initial=10,parameters={'freeze_while_cast':True,'freeze_cast_modes':['manual']})
    rid='rule/talent_eyja_random_sp'
    if negative:
        rid='rule/test_dynamic_loss';data['rules'].append({'id':rid,'kind':'calculation_rule','contract':'resource.recovery',
            'implementation':{'type':'expression','expression':'inputs.current-3'}})
        data['scenarioDraft']['dependencies'].append(rid)
    sim=make(data);sim.ctx.abilities.start('eyja',busy['id'])
    sim.ctx.effects.execute('eyja',[sim.session.world.resolve('eyja')],{'op':'modify_resource','resource':'sp',
        'amount_rule':rid,'parameters':{'random_sample':.3,'respect_recovery_freeze':True}})
    assert sim.ctx.resources.current('eyja','sp')==(7 if negative else 10)
    assert len(events(sim,'resource.recovery_suppressed'))==(0 if negative else 1)
