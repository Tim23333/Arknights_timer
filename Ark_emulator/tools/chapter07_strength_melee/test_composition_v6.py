"""Two same-native-key, different-blackboard variants coexist without conflicts."""
import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_content_composition_v2 import compose_modules
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter07_strength_melee.policies_v2 import providers

ROOT=Path(__file__).resolve().parents[2]
NAMES=('enemy_1078_sotisc','enemy_1083_sotiab','enemy_1083_sotiab_2')
MARKER='buff/ch7/source/enemy_9D0_talent_strength'


def package():
    modules=[]
    for name in NAMES:
        file=ROOT/'packages/campaign/chapter07_strength_melee'/('module.'+name+'.v6.json')
        modules.append((name,json.loads(file.read_bytes())))
    definitions,_=compose_modules(modules)
    units=[m['entities'][0]['id'] for _,m in modules]
    p={'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},
       'definitions':list(definitions.values()),'selectors':[{'id':'selector/strength/combined','kind':'selector',
           'region':{'type':'all'},'filters':[{'tag':'enemy'}]}],
       'scenarioDraft':{'id':'scene/strength/combined','ruleset':'ruleset/ark_standard',
           'map':{'rows':1,'cols':4},'objectives':{},'initialEntities':[
               {'definition':unit,'instanceAlias':name,'position':{'row':0,'col':index}}
               for index,(unit,name) in enumerate(zip(units,NAMES))],
           'scheduledEffects':[{'at':1,'effect':{'op':'apply_buff','selector':'selector/strength/combined','buff':MARKER}},
                               {'at':18,'effect':{'op':'remove_buff','selector':'selector/strength/combined','buff':MARKER}}]}}
    return p


def test_distinct_derived_bindings_same_marker_exact_independent_stats():
    s=Engine.create(Compiler(providers=providers()).compile(package()),providers=providers(),seed=7189)
    s.advance(7)
    assert s.ctx.attributes.value(NAMES[0],'move_speed')==1.1
    assert [s.ctx.attributes.value(name,'atk') for name in NAMES[1:]]==[360,430]
    s.advance(3)
    assert s.ctx.attributes.value(NAMES[0],'move_speed')==1.1*1.3
    assert [s.ctx.attributes.value(name,'atk') for name in NAMES[1:]]==[540,774]
    s.advance(16)
    assert [s.ctx.attributes.value(name,'atk') for name in NAMES[1:]]==[360,430]


def test_each_listener_owns_actual_variant_effects_and_disk_head(tmp_path):
    s=Engine.create(Compiler(providers=providers()).compile(package()),providers=providers(),seed=7190)
    s.advance(7);cp=tmp_path/'strength7.json';pin=write_ordered(cp,s.checkpoint())
    r=Engine.restore(s.program,load_bound(cp,pin),providers=providers());s.advance(19);r.advance(19)
    assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay(),providers=providers()).checkpoint()
    applied=[e for e in s.session.events if e['type']=='buff.applied' and 'enemy_talent_strength[' in e['payload']['buff']]
    removed=[e for e in s.session.events if e['type']=='buff.removed' and 'enemy_talent_strength[' in e['payload']['buff']]
    assert len(applied)==len(removed)==3
    assert all(e['time']==8 for e in applied) and all(e['time']==24 for e in removed)
    assert len({e['payload']['buff'] for e in applied})==3
    assert not any(e['type']=='buff.refreshed' and 'enemy_talent_strength[' in e['payload']['buff'] for e in s.session.events)
