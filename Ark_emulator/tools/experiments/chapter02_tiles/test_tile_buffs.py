"""Actual source operands settle through generic V2 Buff/rule domains."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m26_decision_eligibility_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter02_tile_buff_models import build


def fixture():
    p=build()
    def unit(name,tags):
        return {'id':'unit/'+name,'kind':'entity','tags':tags,'components':{'spatial':{},'attributes':{'base':{'max_hp':1000,'atk':100,'def':10,'mres':0,'attack_speed_ratio':1,'hp_ratio_recovery':0}},
            'resources':{'hp':{'initial':500,'capacity':1000,'role':'health','recovery_rule':'rule/ch2/tile_hp_ratio_recovery','recovery':{'mode':'continuous'}}},
            'abilities':['ability/enter_healing','ability/leave_healing','ability/enter_gazebo','ability/leave_gazebo']}}
    p['entities']=[unit('source',['player']),unit('ground',['enemy','ground']),unit('fly',['enemy','flying'])]
    p['entities'][0]['components']['abilities']+=['ability/ground','ability/fly']
    p['abilities']=[]
    for tile in ('healing','gazebo'):
        for op in ('enter','leave'):
            p['abilities'].append({'id':'ability/'+op+'_'+tile,'kind':'ability','activation':{'mode':'manual','on_start':[{
                'op':'apply_buff' if op=='enter' else 'remove_buff','buff':'buff/ch2/'+('healing_tile_member' if tile=='healing' else 'gazebo_member'),'target':'source'}]},'timeline':[]})
    p['selectors']=[]
    for target in ('ground','fly'):
        p['selectors'].append({'id':'selector/'+target,'kind':'selector','region':{'type':'all'},'filters':[{'tag':'flying' if target=='fly' else 'ground'},{'state':'alive'}],'limit':1})
        p['abilities'].append({'id':'ability/'+target,'kind':'ability','selector':'selector/'+target,'activation':{'mode':'manual','on_start':[{'op':'damage','damage_type':'physical'}]},'timeline':[]})
    p['scenarioDraft']={'id':'scene/ch2_tile_operands','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},'objectives':{},
        'initialEntities':[{'definition':'unit/'+k,'instanceAlias':k,'position':{'row':0,'col':i}} for i,k in enumerate(('source','ground','fly'))]}
    return p


def check(s):
    cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_healing_actual_ratio_public_apply_remove():
    s=Engine.create(Compiler().compile(fixture()),seed=2901)
    s.submit({'action':'skill','source':'source','ability':'ability/enter_healing'},at=0)
    s.submit({'action':'skill','source':'source','ability':'ability/leave_healing'},at=30);s.advance(31)
    assert s.ctx.resources.current('source','hp')==pytest.approx(530)
    assert s.ctx.attributes.value('source','hp_ratio_recovery')==0
    # Attribute value emits events; the public commands replay check uses a
    # separate identical simulation, so no unrecorded query contaminates it.
    s=Engine.create(Compiler().compile(fixture()),seed=2901)
    s.submit({'action':'skill','source':'source','ability':'ability/enter_healing'},at=0)
    s.submit({'action':'skill','source':'source','ability':'ability/leave_healing'},at=30);s.advance(31);check(s)


def test_gazebo_flying_only_damage_and_speed_then_remove():
    s=Engine.create(Compiler().compile(fixture()),seed=2902)
    commands=[(0,'ability/enter_gazebo'),(1,'ability/ground'),(2,'ability/fly'),(3,'ability/leave_gazebo'),(4,'ability/fly')]
    for t,a in commands:s.submit({'action':'skill','source':'source','ability':a},at=t)
    s.advance(5);hits=[e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']
    assert hits==[90,160,90]
    assert s.ctx.resources.current('ground','hp')==410 and s.ctx.resources.current('fly','hp')==250
    check(s)


def test_healing_ratio_uses_effective_max_hp_and_clamps_to_capacity():
    p=fixture();u=p['entities'][0];u['components']['resources']['hp'].update(initial=1980,capacity=2000)
    u['components']['attributes']['base']['max_hp']=1000
    u['components']['attributes']['modifiers']=[{'attribute':'max_hp','layer':'flat','value':1000}]
    s=Engine.create(Compiler().compile(p),seed=2903)
    s.submit({'action':'skill','source':'source','ability':'ability/enter_healing'},at=0);s.advance(11)
    # Effective maxHP2000 gives2 per1/30s: cap after10ticks, never exceed2000.
    assert s.ctx.resources.current('source','hp')==2000
    check(s)


def test_gazebo_speed_is_encoded_to_ratio_and_removed_by_public_command():
    s=Engine.create(Compiler().compile(fixture()),seed=2904)
    s.submit({'action':'skill','source':'source','ability':'ability/enter_gazebo'},at=0)
    s.submit({'action':'skill','source':'source','ability':'ability/leave_gazebo'},at=2);s.advance(1)
    assert s.ctx.attributes.value('source','attack_speed_ratio')==pytest.approx(.8)
    s.advance(2);assert s.ctx.attributes.value('source','attack_speed_ratio')==1
