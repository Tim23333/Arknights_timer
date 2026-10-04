"""Independent kernel model contracts; no native-client approval implied."""
from copy import deepcopy

import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.compare import first_difference
from ark_sim.tools.replay import replay
from test_campaign_acceptance import scene


def engine(data):return Engine.create(Compiler().compile(data),seed=602)
def events(sim,name):return [e for e in sim.session.events if e['type']==name]
def hit(sim,target='target1',**effect):
    sim.ctx.effects.execute('source',[sim.session.world.resolve(target)],{'op':'damage','damage_type':'true',**effect})


def rule(identifier,contract,expression,**fields):
    return {'id':identifier,'kind':'calculation_rule','contract':contract,
        'implementation':{'type':'graph','nodes':[{'id':'out','expression':expression}],'output':'nodes.out'},**fields}


def test_extra_packet_preserves_author_declared_hook_locks():
    data=scene()
    data['entities'][0]['components']['buffs']={'initial':['buff/extra','buff/child_counter']}
    child={'op':'damage','damage_type':'true','scale':2,'parameters':{'damage_hook_locks':['buff/child_counter']}}
    data['rules']=[rule('rule/extra','damage.request',"{'accepted':True,'effect':inputs.effect,'effects':[params.child]}",parameters={'child':child}),
        rule('rule/counter','damage.request',"{'accepted':True,'effect':inputs.effect,'effects':[{'op':'emit','event':'review.unwanted_child_hook'}]}")]
    data['buffs']=[{'id':'buff/extra','kind':'buff','damage_hooks':[{'phase':'before','rule':'rule/extra','condition':'inputs.effect.scale == 1'}]},
        {'id':'buff/child_counter','kind':'buff','damage_hooks':[{'phase':'before','rule':'rule/counter','condition':'inputs.effect.scale == 2'}]}]
    sim=engine(data);hit(sim);sim.advance(1)
    assert sim.ctx.resources.current('target1','hp')==70
    assert not events(sim,'review.unwanted_child_hook')


def test_alias_and_runtime_allocations_for_same_resource_are_merged_before_scaling():
    data=scene();data['entities'][1]['components']['attributes']['base']['factor']=2
    data['entities'][1]['components']['resources']['shield']={'initial':2,'capacity':2}
    data['entities'][1]['components']['buffs']={'initial':['buff/scale']}
    data['rules']=[rule('rule/base','damage.pipeline',"{'accepted':True,'amount':15,'allocations':[{'target':'target1','resource':'hp','delta':-10},{'target':'target','resource':'hp','delta':-5},{'target':'target1','resource':'shield','delta':-1}],'events':[{'type':'review.graph_event','payload':{'value':7}}]}"),
        {'id':'rule/scale','kind':'calculation_rule','contract':'damage.pipeline',
            'metadata':{'input_bindings':{'multiplier':{'entity':'target','attribute':'factor'}}},
            'implementation':{'type':'provider','provider':'ark.damage.settlement_scale'}}]
    data['buffs']=[{'id':'buff/scale','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/scale'}]}]
    data['scenarioDraft']['dependencies']=['rule/base']
    sim=engine(data);hit(sim,rules={'damage.pipeline':'rule/base'});sim.advance(1)
    assert sim.ctx.resources.current('target1','hp')==70
    assert sim.ctx.resources.current('target1','shield')==1
    assert sim.ctx.state()['damage_dealt']==30
    assert events(sim,'damage.accepted')[0]['payload']['amount']==30
    assert events(sim,'review.graph_event')[0]['payload']['value']==7


def test_direct_effect_target_alias_has_same_actual_damage_accounting_as_runtime_id():
    data=scene();data['entities'][1]['components']['resources']['shield']={'initial':2,'capacity':2}
    data['rules']=[rule('rule/alias_settlement','damage.pipeline',"{'accepted':True,'amount':12,'allocations':[{'target':'target','resource':'hp','delta':-12},{'target':'target','resource':'shield','delta':-1}],'events':[]}")]
    data['scenarioDraft']['dependencies']=['rule/alias_settlement']
    sim=engine(data)
    sim.ctx.effects.execute('source',['target1'],{'op':'damage','damage_type':'true','rules':{'damage.pipeline':'rule/alias_settlement'}})
    assert sim.ctx.resources.current('target1','hp')==88
    assert sim.ctx.resources.current('target1','shield')==1
    assert sim.ctx.state()['damage_dealt']==12
    accepted=events(sim,'damage.accepted')[0]['payload']
    assert accepted['amount']==12 and accepted['target']==sim.session.world.resolve('target1')


def test_after_hook_generated_alias_allocations_are_normalized_before_next_scale_hook():
    data=scene();data['entities'][1]['components']['attributes']['base']['factor']=2
    data['entities'][1]['components']['buffs']={'initial':['buff/rewrite','buff/scale']}
    data['rules']=[rule('rule/rewrite','damage.pipeline',"{'accepted':True,'amount':15,'allocations':[{'target':'target1','resource':'hp','delta':-10},{'target':'target','resource':'hp','delta':-5}],'events':[]}"),
        {'id':'rule/scale','kind':'calculation_rule','contract':'damage.pipeline',
            'metadata':{'input_bindings':{'multiplier':{'entity':'target','attribute':'factor'}}},
            'implementation':{'type':'provider','provider':'ark.damage.settlement_scale'}}]
    data['buffs']=[{'id':'buff/rewrite','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/rewrite','priority':2}]},
        {'id':'buff/scale','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/scale','priority':1}]}]
    sim=engine(data);hit(sim)
    assert sim.ctx.resources.current('target1','hp')==70
    assert sim.ctx.state()['damage_dealt']==30


def test_before_hook_failure_after_rng_rolls_back_draws_full_world_and_events():
    data=scene();data['entities'][0]['components']['buffs']={'initial':['buff/fail']}
    data['buffs']=[{'id':'buff/fail','kind':'buff','damage_hooks':[{'phase':'before','rule':'rule/fail','samples':{'stream':'imp','count':2}}]}]
    data['rules']=[rule('rule/fail','damage.request',"{'accepted':True,'effect':inputs.effect,'effects':[{'op':'modify_resource','resource':'missing','delta':1}]}")]
    sim=engine(data);before=deepcopy(sim.checkpoint());log=deepcopy(sim.session.events)
    with pytest.raises(ValueError,match='absent'):hit(sim)
    assert sim.checkpoint()==before and sim.session.events==log
    assert len(sim.session.random.samples)==0


def test_late_second_target_hook_failure_rolls_back_first_target_and_rng():
    data=scene();data['entities'][1]['components']['buffs']={'initial':['buff/reject_late']}
    data['rules']=[rule('rule/reject_late','damage.pipeline',"inputs.effect.settlement if inputs.target.components.spatial.position.col == 2 else {'accepted':True,'amount':1/0,'allocations':[],'events':[]}")]
    data['buffs']=[{'id':'buff/reject_late','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/reject_late','samples':{'stream':'imp','count':1}}]}]
    sim=engine(data);before=deepcopy(sim.checkpoint())
    with pytest.raises(ValueError):
        sim.ctx.effects.execute('source',[sim.session.world.resolve('target1'),sim.session.world.resolve('target2')],{'op':'damage','damage_type':'true'})
    assert sim.checkpoint()==before


def test_source_and_target_hook_rejections_never_commit_source_extra_effects():
    data=scene();data['entities'][0]['components']['buffs']={'initial':['buff/extra']}
    data['entities'][1]['components']['buffs']={'initial':['buff/cancel']}
    data['rules']=[rule('rule/extra','damage.request',"{'accepted':True,'effect':inputs.effect,'effects':[{'op':'emit','event':'review.extra'}]}"),
        rule('rule/cancel','damage.pipeline',"{'accepted':False,'amount':0,'allocations':[],'events':[]}")]
    data['buffs']=[{'id':'buff/extra','kind':'buff','damage_hooks':[{'phase':'before','rule':'rule/extra'}]},
        {'id':'buff/cancel','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/cancel'}]}]
    sim=engine(data);hit(sim);sim.advance(1)
    assert not events(sim,'review.extra')
    assert sim.ctx.resources.current('target1','hp')==100
    assert len(events(sim,'damage.rejected'))==1


def test_group_condition_precedes_arbitration_and_sampling():
    data=scene();data['entities'][1]['components']['buffs']={'initial':['buff/high','buff/low']}
    data['rules']=[rule('rule/low','damage.pipeline',"{'accepted':True,'amount':17,'allocations':[],'events':[]}")]
    data['buffs']=[{'id':'buff/'+name,'kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/low','group':'test',
        'priority':priority,'condition':condition,'samples':{'stream':'imp','count':1}}]}
        for name,priority,condition in [('high',9,'False'),('low',1,'True')]]
    sim=engine(data);hit(sim)
    assert sim.ctx.resources.current('target1','hp')==83
    assert len(sim.session.random.samples)==1


def test_ability_heal_immunity_override_matches_selection_and_settlement():
    data=scene();target=data['entities'][1]['components']
    target['resources']['hp']['initial']=10
    target['resources']['hp']['parameters']={'healing_allowed':False}
    data['abilities'][0]['parameters']={'healing':True,'ignore_heal_immunity':True}
    data['selectors'][0]['limit']=1
    data['abilities'][0]['timeline']=[{'at':0,'effect':{'op':'heal'}}]
    sim=engine(data);sim.submit({'action':'skill','source':'source','ability':'ability/probe'});sim.advance(1)
    assert sim.ctx.resources.current('target1','hp')==20
    assert len(events(sim,'healing.accepted'))==1 and not events(sim,'healing.rejected')


def spawn_model():
    data=scene()
    data['scenarioDraft']['resources']={'dp':{'initial':0,'capacity':99}}
    data['entities'].append({'id':'unit/owned_card','kind':'entity','tags':['player','token'],
        'components':{'attributes':{'base':{'max_hp':100,'deploy_cost':10,'redeploy_time':0}},
            'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},
            'deployable':{'policy':'policy/ark_ground_deploy','terrain':'ground','refund_ratio':1},
            'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    data['abilities'][0]={'id':'ability/probe','kind':'ability','activation':{'mode':'manual',
        'on_start':[{'op':'spawn','definition':'unit/owned_card','owner':'source',
            'parameters':{'position_from_payload':True,'max_owned':1}}]},'timeline':[]}
    return data


def test_free_owned_spawn_records_zero_actual_payment_and_cannot_mint_refund():
    sim=engine(spawn_model())
    sim.submit({'action':'skill','source':'source','ability':'ability/probe',
        'payload':{'position':{'row':0,'col':1},'facing':'right'}});sim.advance(1)
    child=next(e['id'] for e in sim.session.world.entities() if e['definition_id']=='unit/owned_card')
    assert sim.ctx.resources.current('system/battle','dp')==0
    assert sim.ctx.get(child,('deployable','paid_cost'))==0
    sim.submit({'action':'withdraw','source':child});sim.advance(1)
    assert sim.ctx.resources.current('system/battle','dp')==0


@pytest.mark.parametrize('failure',['tile','occupied','capacity'])
def test_owned_deployment_rejects_shared_eligibility_failure_atomically(failure):
    data=spawn_model();data['scenarioDraft']['resources']['dp']['initial']=30
    data['abilities'][0]['activation']['costs']=[{'owner':'battle','resource':'dp','amount':5}]
    if failure=='tile':
        data['scenarioDraft']['map']['tiles']=[{'tileKey':'tile_floor','passableMask':1,'buildableType':2} for _ in range(5)]
    if failure=='occupied':
        data['scenarioDraft']['initialEntities'].append({'definition':'unit/owned_card','instanceAlias':'existing','position':{'row':0,'col':1}})
    if failure=='capacity':data['scenarioDraft']['parameters']={'deploy_capacity':0}
    sim=engine(data);before=deepcopy(sim.checkpoint())
    with pytest.raises(ValueError):
        sim.ctx.abilities.start('source','ability/probe',event_payload={'position':{'row':0,'col':1},'facing':'right'})
    assert sim.checkpoint()==before


def switch_model():
    data=scene(mode='automatic_attack');data['selectors'][0]['limit']=1
    data['entities'][0]['components']['attributes']['base']['attack_interval']=1
    data['entities'][0]['components']['resources']['mode']={'initial':0,'capacity':1}
    data['abilities'][0]['activation']['condition']='inputs.resources.mode.current == 0'
    data['abilities'][0]['timeline']=[{'at':3,'effect':{'op':'damage','damage_type':'true'}}]
    data['abilities'] += [{'id':'ability/switch','kind':'ability','activation':{'mode':'manual',
        'on_start':[{'op':'modify_resource','target':'source','resource':'mode','value':1}]},
        'parameters':{'blocks_attacks':False,'reset_attack_clock':True,'cancel_pending_attacks':True},'timeline':[]},
        {'id':'ability/new_attack','kind':'ability','activation':{'mode':'automatic_attack',
            'condition':'inputs.resources.mode.current == 1'},'selector':'selector/probe',
            'timeline':[{'at':0,'effect':{'op':'damage','damage_type':'true','scale':2}}]}]
    data['entities'][0]['components']['abilities'] += ['ability/switch','ability/new_attack']
    return data


def test_failed_mode_start_restores_cancelled_task_clock_and_public_history():
    data=switch_model();data['abilities'][1]['activation']['on_start'].append(
        {'op':'modify_resource','target':'source','resource':'sp','amount_rule':'rule/late_failure'})
    data['rules']=[rule('rule/late_failure','resource.recovery','1/0')]
    sim=engine(data);sim.advance(1)
    before=deepcopy(sim.checkpoint());log=deepcopy(sim.session.events)
    with pytest.raises(ValueError):sim.ctx.abilities.start('source','ability/switch')
    assert sim.checkpoint()==before and sim.session.events==log
    sim.advance(3)
    assert sim.ctx.resources.current('target1','hp')==90
    assert not events(sim,'ability.interrupted')


def test_mode_switch_cancels_unlaunched_packet_and_restarts_new_clock_immediately():
    sim=engine(switch_model());sim.advance(1)
    sim.submit({'action':'skill','source':'source','ability':'ability/switch'});sim.advance(4)
    hits=events(sim,'damage.accepted')
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(1,20)]
    assert sim.ctx.get('source',('runtime','next_attack'))==31


def event_model(delay=0):
    data=scene();component=data['entities'][0]['components']
    component['resources']['sp']['parameters']={'freeze_while_cast':True,'freeze_cast_modes':['manual']}
    component['buffs']={'initial':['buff/event']}
    component['abilities'] += ['ability/hold']
    data['abilities'][0].pop('selector')
    data['abilities'][0]['parameters']={'blocks_attacks':False}
    data['abilities'][0]['timeline']=[{'at':1,'effect':{'op':'emit','event':'review.pulse'}}]
    data['abilities'].append({'id':'ability/hold','kind':'ability','activation':{'mode':'manual'},'duration_seconds':1/30,'timeline':[]})
    grant={'op':'modify_resource','resource':'sp','delta':4,'parameters':{'respect_recovery_freeze':True}}
    if delay:grant={'op':'schedule','delay_seconds':delay,'effect':grant}
    data['buffs']=[{'id':'buff/event','kind':'buff','events':[{'event':'review.pulse','effects':[grant]}]}]
    return data


@pytest.mark.parametrize('delay',[0,.1])
def test_emission_freeze_snapshot_survives_finish_and_nested_scheduling(delay):
    sim=engine(event_model(delay));sim.ctx.abilities.start('source','ability/probe')
    sim.ctx.abilities.start('source','ability/hold');sim.advance(6)
    assert sim.ctx.resources.current('source','sp')==0
    assert len(events(sim,'resource.recovery_suppressed'))==1


def test_captured_unfrozen_grant_does_not_change_when_recipient_starts_new_cast():
    data=event_model(.1);data['abilities'][0]['activation'].update(mode='passive',event='review.external_start')
    data['abilities'][1]['duration_seconds']=1
    sim=engine(data);sim.ctx.abilities.start('source','ability/probe',automatic=True);sim.advance(2)
    sim.ctx.abilities.start('source','ability/hold')
    sim.advance(4)
    assert sim.ctx.resources.current('source','sp')==4


def test_random_transaction_checkpoints_replay_during_delayed_packet_are_identical():
    data=scene();data['entities'][0]['components']['buffs']={'initial':['buff/sample']}
    data['buffs']=[{'id':'buff/sample','kind':'buff','damage_hooks':[{'phase':'before','rule':'rule/echo',
        'samples':{'stream':'imp','count':1}}]}]
    data['rules']=[rule('rule/echo','damage.request',"{'accepted':True,'effect':inputs.effect,'effects':[]}")]
    program=Compiler().compile(data);sim=Engine.create(program,seed=602)
    for at in (0,2,4):sim.submit({'action':'skill','source':'source','ability':'ability/probe'},at=at)
    sim.advance(1);restored=Engine.restore(program,sim.checkpoint());sim.advance(5);restored.advance(5)
    assert len(sim.session.random.samples)==6
    assert first_difference(sim.snapshot(),restored.snapshot()) is None
    assert first_difference(sim.snapshot(),replay(program,sim.export_replay()).snapshot()) is None


def paid_spawn_model(amounts):
    data=spawn_model();data['scenarioDraft']['resources']['dp']['initial']=12
    deploy=data['entities'][-1]['components']['deployable']
    deploy['parameters']={'max_instances':len(amounts)}
    # Move the first actual child away before the second deployment. This
    # keeps the real occupied-tile policy and isolates payment allocation.
    data['selectors'].append({'id':'selector/review_owned','kind':'selector','region':{'type':'all'},
        'filters':[{'tag':'token'},{'owner':'source'},{'state':'alive'}],'limit':None})
    prototype=data['abilities'][0]['activation']['on_start'][0]
    data['abilities'][0]['activation']['on_start']=[]
    for amount in amounts:
        effect=deepcopy(prototype);effect['parameters'].update(max_owned=len(amounts),deployment_payment_amount=amount)
        data['abilities'][0]['activation']['on_start'].append(effect)
        if len(data['abilities'][0]['activation']['on_start'])==1 and len(amounts)>1:
            data['abilities'][0]['activation']['on_start'].append({'op':'move','selector':'selector/review_owned',
                'offset':{'row':0,'col':1}})
    data['abilities'][0]['activation']['costs']=[{'owner':'battle','resource':'dp','amount':5}]
    return data


def test_multiple_owned_spawns_share_actual_payment_without_multiplying_refunds():
    sim=engine(paid_spawn_model([2,3]))
    sim.submit({'action':'skill','source':'source','ability':'ability/probe','payload':{'position':{'row':0,'col':1}}});sim.advance(1)
    children=[e['id'] for e in sim.session.world.entities() if e['definition_id']=='unit/owned_card']
    assert len(children)==2 and [sim.ctx.get(c,('deployable','paid_cost')) for c in children]==[2,3]
    assert sim.ctx.resources.current('system/battle','dp')==7
    for child in children:sim.submit({'action':'withdraw','source':child})
    sim.advance(1)
    assert sim.ctx.resources.current('system/battle','dp')==12


def test_overallocated_second_owned_spawn_rolls_back_first_spawn_and_payment():
    sim=engine(paid_spawn_model([3,3]));before=deepcopy(sim.checkpoint())
    with pytest.raises(ValueError,match='unallocated'):
        sim.ctx.abilities.start('source','ability/probe',event_payload={'position':{'row':0,'col':1}})
    assert sim.checkpoint()==before


def test_negative_owned_deployment_payment_claim_is_rejected_atomically():
    with pytest.raises(ValueError,match='must be >= 0'):engine(paid_spawn_model([-2]))


def test_overlapping_input_locks_release_only_the_matching_key_before_commands():
    data=scene();data['selectors'][0]['limit']=1
    data['scenarioDraft']['scheduledEffects']=[{'at':at,'effect':{'op':'input_lock','target':'battle',
        'parameters':{'key':key,'enabled':enabled}}} for at,key,enabled in
        [(0,'story',True),(0,'tutorial',True),(1,'story',False),(2,'tutorial',False)]]
    sim=engine(data)
    for at in (0,1,2):sim.submit({'action':'skill','source':'source','ability':'ability/probe'},at=at)
    sim.advance(3)
    assert len(events(sim,'command.rejected'))==2
    assert sim.ctx.resources.current('target1','hp')==90
    assert sim.ctx.state().get('input_locks',[])==[]


def test_scheduled_random_effect_failure_rolls_back_lock_draw_and_resource_changes():
    data=scene()
    data['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'random','target':'battle','stream':'imp','probability':1,
        'on_success':[{'op':'input_lock','parameters':{'key':'failed_story','enabled':True}},
            {'op':'modify_resource','resource':'missing','delta':1}]}}]
    sim=engine(data);before=deepcopy(sim.checkpoint())
    with pytest.raises(ValueError,match='absent'):sim.advance(1)
    assert sim.ctx.state().get('input_locks',[])==[]
    assert not sim.session.random.samples
    after=sim.checkpoint()
    for store in ('world','events','random'):assert after['kernel'][store]==before['kernel'][store]
    assert after['kernel']['failure']['exception']=='ValueError'
    with pytest.raises(RuntimeError,match='restore a valid checkpoint'):sim.advance(1)
    # The scheduler has popped the failed task and the kernel keeps failure
    # diagnostics. Restoring a valid checkpoint is required to resume.
    assert Engine.restore(sim.program,before).checkpoint()==before
