"""Actual typed source range, single arrow, live damage and retained flight."""
import json
from copy import deepcopy

from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter09_ordinary.build_dubow_v1 import OUTFILE,build,providers


def package():
    p=json.loads(OUTFILE.read_bytes());p['entities'].append({'id':'unit/c9/arrow/receiver','kind':'entity','tags':['player'],
       'components':{'attributes':{'base':{'max_hp':5000,'atk':0,'def':137,'mres':83}},
         'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'spatial':{},
         'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'},
         'abilities':['ability/c9/arrow/retire']}})
    p['selectors'].append({'id':'selector/c9/arrow/enemy','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}]})
    p['abilities'].append({'id':'ability/c9/arrow/retire','kind':'ability','activation':{'mode':'manual'},
                          'selector':'selector/c9/arrow/enemy','timeline':[{'at':0,'effect':{'op':'retire','parameters':{'reason':'withdrawn'}}}]})
    p['scenarioDraft']={'id':'scene/c9/arrow/source','ruleset':'ruleset/ark_standard','map':{'rows':1,'cols':5},
        'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'enemy','position':{'row':0,'col':0}},
                           {'definition':'unit/c9/arrow/receiver','instanceAlias':'target','position':{'row':0,'col':2}}]}
    return p


def proof(p,tmp_path,split,end):
    registry=providers();program=Compiler(providers=registry).compile(p);s=Engine.create(program,providers=registry,seed=91619)
    s.session.advance(split);path=tmp_path/'inflight.checkpoint.json';pin=write_ordered(path,s.checkpoint())
    restored=Engine.restore(program,load_bound(path,pin),providers=registry);s.session.advance(end-split);restored.session.advance(end-split)
    head=replay(program,s.export_replay(),providers=registry)
    assert s.checkpoint()==restored.checkpoint()==head.checkpoint()
    assert list(s.session.events)==list(restored.session.events)==list(head.session.events)
    return s


def test_shared_combat_attack_node_has_one_source_arrow21_hit27_damage113(tmp_path):
    assert json.loads(OUTFILE.read_bytes())==build();s=proof(package(),tmp_path,24,35)
    launch=[e for e in s.session.events if e['type']=='projectile.launched']
    hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(launch)==1 and launch[0]['time']==21
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(27,113)]
    assert s.ctx.resources.current('target','hp')==4887 and s.ctx.attributes.value('enemy','mres')==70


def test_source_retire22_after_arrow21_keeps_original113_actual_hit27(tmp_path):
    p=package();p['scenarioDraft']['commands']=[{'at':22,'action':'skill','source':'target','ability':'ability/c9/arrow/retire'}]
    s=proof(p,tmp_path,24,35);hits=[e for e in s.session.events if e['type']=='damage.accepted']
    assert not s.ctx.active('enemy') and s.ctx.resources.current('enemy','hp')==3800
    assert [(e['time'],e['payload']['amount']) for e in hits]==[(27,113)]


def test_source_range2_rejects_outside_or_targetfree_or_camo_or_flying(tmp_path):
    for label,position,changes in [('outside',3,{}),('targetfree',2,{'target_free':True}),('camo',2,{'camouflage':True}),('air',2,{'motion':2})]:
        p=package();p['scenarioDraft']['initialEntities'][1]['position']['col']=position
        p['entities'][1]['components']['selection_state'].update(changes)
        s=proof(p,tmp_path,13,35)
        assert not [e for e in s.session.events if e['type']=='projectile.launched'],label
        assert s.ctx.resources.current('target','hp')==5000
