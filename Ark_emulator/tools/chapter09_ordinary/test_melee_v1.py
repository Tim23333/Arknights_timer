"""Actual source damage, silenceable MRES, clocks and ordered recovery."""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_ordinary.build_melee_v1 import build,OUT


def package(key):
    p=json.loads((OUT/(key+'.module.v1.json')).read_bytes())
    p['entities'].append({'id':'unit/c9/fixture/blocker','kind':'entity','tags':['player'],
       'components':{'attributes':{'base':{'max_hp':20000,'atk':1000,'def':137,'mres':23,'block_count':1}},
         'resources':{'hp':{'initial':20000,'capacity':20000,'role':'health'}},'spatial':{},
         'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},
         'abilities':['ability/c9/fixture/silence','ability/c9/fixture/unmute','ability/c9/fixture/arts'],
         'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['buffs'].append({'id':'buff/c9/fixture/silence','kind':'buff','selection_flags':{'abnormal_flags':[12]}})
    p['selectors'].append({'id':'selector/c9/fixture/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
    effects=[('silence',{'op':'apply_buff','buff':'buff/c9/fixture/silence'}),
             ('unmute',{'op':'remove_buff','buff':'buff/c9/fixture/silence'}),
             ('arts',{'op':'damage','damage_type':'arts','scale':1})]
    for name,effect in effects:
        p['abilities'].append({'id':'ability/c9/fixture/'+name,'kind':'ability','selector':'selector/c9/fixture/enemy',
                              'activation':{'mode':'manual'},'timeline':[{'at':0,'effect':effect}]})
    p['scenarioDraft']={'id':'scene/c9/source/'+key,'ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':3},
        'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':0,'col':1}},
                           {'definition':'unit/c9/fixture/blocker','instanceAlias':'player','position':{'row':0,'col':1}}]}
    return p


def proof(p,tmp_path,split,end):
    program=Compiler().compile(p);s=Engine.create(program,seed=916)
    s.session.advance(split);path=tmp_path/'checkpoint.json';pin=write_ordered(path,s.checkpoint())
    restored=Engine.restore(program,load_bound(path,pin));s.session.advance(end-split);restored.session.advance(end-split)
    head=replay(program,s.export_replay())
    assert s.checkpoint()==restored.checkpoint()==head.checkpoint()
    assert list(s.session.events)==list(restored.session.events)==list(head.session.events)
    return s


@pytest.mark.parametrize('key,atk,cycle',[('enemy_1165_duhond',300,42),('enemy_1166_dusbr',280,60)])
def test_original_module_rebuild_source18_hit_fullduration_and_three_damage_packets(key,atk,cycle,tmp_path):
    assert json.loads((OUT/(key+'.module.v1.json')).read_bytes())==build(key)
    s=proof(package(key),tmp_path,17,141)
    hits=[event for event in s.session.events if event['type']=='damage.accepted' and event['payload']['source']==s.session.world.resolve('enemy')]
    assert [(event['time'],event['payload']['amount']) for event in hits[:3]]==[(18,atk-137),(18+cycle,atk-137),(18+2*cycle,atk-137)]
    assert s.ctx.attributes.value('enemy','mres')==70
    assert len([buff for buff in s.ctx.get('enemy',('buffs','instances')) if buff['definition'].endswith('/refracting')])==1


@pytest.mark.parametrize('key',['enemy_1165_duhond','enemy_1166_dusbr'])
def test_actual_arts_damage300_then1000_during_silence_then300_restored(key,tmp_path):
    p=package(key)
    p['scenarioDraft']['commands']=[{'at':tick,'action':'skill','source':'player','ability':'ability/c9/fixture/'+name}
            for tick,name in [(2,'arts'),(4,'silence'),(6,'arts'),(8,'unmute'),(10,'arts')]]
    s=proof(p,tmp_path,5,12)
    hits=[event['payload']['amount'] for event in s.session.events if event['type']=='damage.accepted' and event['payload']['source']==s.session.world.resolve('player')]
    assert hits==[300.00000000000006,1000,300.00000000000006]
    assert s.ctx.attributes.value('enemy','mres')==70
    assert s.ctx.resources.current('enemy','hp')==p['entities'][0]['components']['attributes']['base']['max_hp']-sum(hits)
