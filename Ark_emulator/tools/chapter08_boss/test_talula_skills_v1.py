"""Actual original skill clocks and mode payloads, no stage completion claim."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_selection_context_clock_v1_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
from tools.chapter08_boss.build_talula_skills_v1 import OUT,build,sha,CORE
from tools.chapter08_boss.talula_skill_policies_v1 import providers
from tools.chapter08_boss.build_dragon_fire_v1 import TIMER

def package(which='dragon_fire',mode=0):
    assert sha(OUT)=='5a912b165a7d87fd9ba5547a62ddd9aa883775288edb3d5a09c7fe7c71a29d2c'
    p=json.loads(OUT.read_bytes());unit=p['entities'][0]['components'];aid='ability/ch8/talula/'+str(mode)+'/'+which
    # Isolation selects one source skill; keeps its original clocks and Boss numeric data.
    unit['abilities']=[aid];unit.pop('ability_arbitration');p['behaviors'][0].pop('decision');p['entities'][0]['metadata']['isolated_author_skill']=aid
    p['entities'].append({'id':'unit/ch8/skill/player','kind':'entity','tags':['player'],'components':{
        'attributes':{'base':{'atk':0,'max_hp':10000,'def':813,'mres':27}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
        'spatial':{},'selection_state':{'side':0,'motion':1,'category':1,'unit_type':1},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']={'id':'scene/ch8/talula/skill_author','ruleset':'ruleset/ark_standard','map':{'rows':3,'cols':6},'seed':81617,
        'initialEntities':[{'definition':p['entities'][0]['id'],'instanceAlias':'boss','position':{'row':1,'col':1}},
            {'definition':'unit/ch8/skill/player','instanceAlias':'target','position':{'row':1,'col':2}}]}
    if mode:
        p['selectors'].append({'id':'selector/ch8/skill/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'boss'}]})
        p['scenarioDraft']['scheduledEffects']=[{'at':0,'effect':{'op':'modify_resource','selector':'selector/ch8/skill/boss','resource':'hp','value':25000}}]
    return p,aid

def proof(p,tmp_path,split,end):
    reg=providers();program=Compiler(providers=reg).compile(p);s=Engine.create(program,providers=reg);s.advance(split)
    cp=tmp_path/'actual.cp.json';h=write_ordered(cp,s.checkpoint());r=Engine.restore(program,load_bound(cp,h),providers=reg)
    s.advance(end-split);r.advance(end-split);head=replay(program,s.export_replay(),providers=reg)
    assert s.snapshot()==r.snapshot()==head.snapshot() and list(s.session.events)==list(r.session.events)==list(head.session.events)
    return s

def test_exact8abilities_and_four_source_cooldowns_rebuild():
    p=build();assert json.loads(OUT.read_bytes())==p
    skills=[a for a in p['abilities'] if a['activation']['mode']=='manual']
    assert [(a['initial_cooldown_seconds'],a['cooldown_seconds']) for a in skills]==[(19,19),(160,40),(7,7),(15,15)]

def test_source_dragon19_firststart570_apply600_tick630first56(tmp_path):
    p,aid=package();s=proof(p,tmp_path,580,700)
    assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==aid]==[570]
    assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(630,56),(660,62),(690,68)]
    assert [e['time'] for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==TIMER]==[600]

def test_half_dragon7_firststart210_apply240_excludes_already_burned(tmp_path):
    p,aid=package(mode=1);s=proof(p,tmp_path,220,750)
    assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==aid]==[210]
    assert [e['time'] for e in s.session.events if e['type']=='buff.applied' and e['payload']['buff']==TIMER]==[240]
    assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[50+6*n for n in range(1,17)]

def test_source_dance160_firststart4800_effect4865_not40_override(tmp_path):
    p,aid=package('dance_fire');s=proof(p,tmp_path,4820,4900)
    assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==aid]==[4800]
    assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(4865,1095)]

def test_half_dance15_two_targets_515_each1095_cycle450(tmp_path):
    p,aid=package('dance_fire',1);p['scenarioDraft']['initialEntities'].append({'definition':'unit/ch8/skill/player','instanceAlias':'second','position':{'row':2,'col':2}})
    s=proof(p,tmp_path,470,990)
    assert [e['time'] for e in s.session.events if e['type']=='ability.started' and e['payload']['ability']==aid]==[450,900]
    assert [(e['time'],e['payload']['amount']) for e in s.session.events if e['type']=='damage.accepted']==[(515,1095),(515,1095),(965,1095),(965,1095)]
