"""Independent boundary/ownership counterexamples discovered in peer review."""
from copy import deepcopy

import pytest

from ark_sim import Compiler,Engine
from ark_sim.tools.compare import first_difference


def review_scene(aura=True,delay=0):
    player={'id':'unit/reviewer','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'atk':10,'max_hp':100,'def':0,'mres':0}},
        'resources':{'hp':{'initial':100,'capacity':100,'role':'health'}},'spatial':{},'abilities':['ability/review_shot']}}
    enemy={'id':'unit/review_enemy','kind':'entity','tags':['enemy'],'components':{
        'attributes':{'base':{'atk':0,'max_hp':1000,'def':0,'mres':0}},
        'resources':{'hp':{'initial':1000,'capacity':1000,'role':'health'}},'spatial':{}}}
    package={'schemaVersion':2,'entities':[player,enemy],'abilities':[{
        'id':'ability/review_shot','kind':'ability','activation':{'mode':'manual'},'selector':'selector/review_enemy',
        'timeline':[{'at':delay,'effect':{'op':'damage','damage_type':'physical','read_mode':{'source_attributes':'at_cast'}}}]}],
        'selectors':[{'id':'selector/review_enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1},
                     {'id':'selector/review_aura','kind':'selector','region':{'type':'radius','radius':1},'filters':[{'state':'alive'}]}],
        'buffs':[{'id':'buff/review_emitter','kind':'buff','duration_seconds':1},
                 {'id':'buff/review_member','kind':'buff','stacking':{'mode':'independent'},
                  'modifiers':[{'attribute':'atk','layer':'flat','value':5}]}],
        'scenarioDraft':{'id':'scenario/aura_review','ruleset':'ruleset/ark_standard',
            'dependencies':['buff/review_emitter'],'map':{'rows':1,'cols':4},'initialEntities':[
                {'definition':player['id'],'instanceAlias':'caster','position':{'row':0,'col':0}},
                {'definition':enemy['id'],'instanceAlias':'enemy','position':{'row':0,'col':1}}]}}
    if aura:package['buffs'][0]['aura']={'selector':'selector/review_aura','buff':'buff/review_member'}
    else:package['buffs'][0]['modifiers']=[{'attribute':'atk','layer':'flat','value':5}]
    return package


def engine(data):
    return Engine.create(Compiler().compile(data),seed=31)


def children(sim,alias):
    return [b for b in sim.ctx.get(alias,('buffs','instances')) if b['definition']=='buff/review_member']


@pytest.mark.parametrize('aura',[True,False])
def test_input_at_expiry_reads_ten_not_expired_fifteen(aura):
    sim=engine(review_scene(aura))
    sim.ctx.buffs.apply('caster','caster','buff/review_emitter')
    sim.submit({'action':'activate_ability','source':'caster','ability':'ability/review_shot'},at=30)
    sim.advance(31)
    assert sim.ctx.resources.current('enemy','hp')==990
    assert sim.ctx.attributes.value('caster','atk')==10
    hits=[e for e in sim.session.events if e['type']=='damage.accepted']
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(30,10)]


def test_direct_ability_at_expiry_prunes_before_cast_snapshot():
    sim=engine(review_scene())
    sim.ctx.buffs.apply('caster','caster','buff/review_emitter');sim.advance(30)
    sim.ctx.abilities.start('caster','ability/review_shot')
    sim.advance(1)
    assert sim.ctx.resources.current('enemy','hp')==990


def test_historical_at_cast_snapshot_keeps_fifteen_after_expiry():
    sim=engine(review_scene(delay=2))
    sim.ctx.buffs.apply('caster','caster','buff/review_emitter')
    sim.submit({'action':'activate_ability','source':'caster','ability':'ability/review_shot'},at=29)
    sim.advance(32)
    assert sim.ctx.attributes.value('caster','atk')==10
    assert sim.ctx.resources.current('enemy','hp')==985
    hits=[e for e in sim.session.events if e['type']=='damage.accepted']
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(31,15)]


def test_two_sources_same_center_keep_distinct_children_and_remove_only_own_parent():
    data=review_scene();secondary=deepcopy(data['entities'][0]);secondary['id']='unit/secondary';secondary['components']['abilities']=[]
    data['entities'].append(secondary)
    data['scenarioDraft']['initialEntities'].append({'definition':secondary['id'],'instanceAlias':'secondary','position':{'row':0,'col':3}})
    sim=engine(data)
    first=sim.ctx.buffs.apply('caster','caster','buff/review_emitter')
    second=sim.ctx.buffs.apply('secondary','caster','buff/review_emitter')
    assert sim.ctx.attributes.value('caster','atk')==20
    assert {b['aura_parent'] for b in children(sim,'caster')}=={first,second}
    sim.ctx.buffs.remove('caster',first)
    assert sim.ctx.attributes.value('caster','atk')==15
    assert len(children(sim,'caster'))==1 and children(sim,'caster')[0]['aura_parent']==second
    sim.ctx.lifecycle.retire('secondary','withdrawn')
    assert sim.ctx.attributes.value('caster','atk')==10
    assert children(sim,'caster')==[] and children(sim,'enemy')==[]


def test_effect_phase_displacement_leaves_no_one_tick_member():
    data=review_scene();data['entities'][1]['components']['abilities']=['ability/review_leave']
    data['abilities'].append({'id':'ability/review_leave','kind':'ability','activation':{'mode':'manual'},
        'timeline':[{'at':0,'effect':{'op':'move','target':'self','position':{'row':0,'col':3}}}]})
    sim=engine(data);sim.ctx.buffs.apply('caster','caster','buff/review_emitter')
    assert sim.ctx.attributes.value('enemy','atk')==5
    sim.submit({'action':'activate_ability','source':'enemy','ability':'ability/review_leave'});sim.advance(1)
    assert sim.ctx.attributes.value('enemy','atk')==0
    assert children(sim,'enemy')==[]


def test_failed_member_effect_restores_entire_atomic_checkpoint():
    data=review_scene();data['buffs'][1]['effects']=[{'op':'modify_resource','resource':'absent','delta':1}]
    sim=engine(data);before=sim.checkpoint()
    with pytest.raises(ValueError):sim.ctx.buffs.apply('caster','caster','buff/review_emitter')
    assert first_difference(before,sim.checkpoint()) is None
