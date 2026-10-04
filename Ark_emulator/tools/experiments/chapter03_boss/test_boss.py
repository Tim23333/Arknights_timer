import sys,json
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
def fixture(target=False):
    p=json.loads((ROOT/'packages/campaign/chapter03_models/skulsr.level1.reference.json').read_bytes());boss=p['entities'][0]['id']
    director={'id':'unit/director','kind':'entity','components':{'spatial':{},'abilities':['ability/hp14999','ability/hp15000','ability/dead','ability/hp18000']}}
    p['entities'].append(director);p['selectors'].append({'id':'selector/boss','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
    p['abilities'] += [{'id':'ability/'+name,'kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'modify_resource','resource':'hp','value':value}]},'timeline':[]} for name,value in [('hp14999',14999),('hp15000',15000),('dead',0),('hp18000',18000)]]
    initial=[{'definition':boss,'instanceAlias':'boss','position':{'row':3,'col':0}},{'definition':'unit/director','instanceAlias':'director','position':{'row':0,'col':0}}]
    if target:
        p['entities'].append({'id':'unit/target','kind':'entity','tags':['player'],'components':{'spatial':{},'attributes':{'base':{'max_hp':10000,'def':100,'mres':0}},'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}}}})
        initial.append({'definition':'unit/target','instanceAlias':'target','position':{'row':3,'col':1}})
    p['scenarioDraft']={'id':'scene/ch3/boss','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':7,'cols':7},'initialEntities':initial};return p
def make(p=None):return Engine.create(Compiler().compile(p or fixture()),seed=3811)

def test_exact_level1_stats_and_half_threshold_before_and_after():
    p=fixture();s=make(p);assert s.ctx.resources.current('boss','hp')==30000
    s.submit({'action':'skill','source':'director','ability':'ability/hp15000'},at=0);s.advance(1);assert s.ctx.resources.current('boss','mode')==0
    s.submit({'action':'skill','source':'director','ability':'ability/hp14999'},at=1);s.advance(1);assert s.ctx.resources.current('boss','mode')==1
    s.submit({'action':'skill','source':'director','ability':'ability/hp15000'},at=2);s.advance(1);assert s.ctx.resources.current('boss','mode')==0
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()

def test_effective_maxHP_change_uses_ratio_not_literal15000_or5250():
    p=fixture();p['scenarioDraft']['initialEntities'][0]['components']={'attributes':{'base':{'max_hp':40000}}}
    s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/hp18000'},at=0);s.advance(1)
    assert s.ctx.get('boss',('resources','hp','observed_capacity'))==40000 and s.ctx.resources.current('boss','mode')==1

def test_maxHP_modifier_change_restores_phase_when_current_HP_exceeds_new_half():
    p=fixture();p['buffs'].append({'id':'buff/maxhp','kind':'buff','modifiers':[{'attribute':'max_hp','layer':'direct_ratio','value':-.5}]})
    p['abilities'].append({'id':'ability/cap','kind':'ability','selector':'selector/boss','activation':{'mode':'manual','on_start':[{'op':'apply_buff','buff':'buff/maxhp'}]},'timeline':[]});p['entities'][-1]['components']['abilities'].append('ability/cap')
    s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/hp14999'},at=0);s.advance(1);assert s.ctx.resources.current('boss','mode')==1
    s.submit({'action':'skill','source':'director','ability':'ability/cap'},at=1);s.advance(1);assert s.ctx.get('boss',('resources','hp','observed_capacity'))==15000 and s.ctx.resources.current('boss','mode')==0

def test_zeroHP_never_enters_lowHP_mode_or_loops():
    p=fixture();s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/dead'},at=0);s.advance(3)
    assert not s.ctx.alive('boss') and not any(e['type']=='ability.started' and e['payload'].get('ability')=='ch3/ability/skulsr_enter' for e in s.session.events)

def test_level1_normal_and_lowHP_ranged_damage_frames_disk_replay(tmp_path):
    p=fixture(True);program=Compiler().compile(p);s=Engine.create(program,seed=3812);s.advance(10);path=tmp_path/'boss.json';h=write_ordered(path,s.checkpoint());r=Engine.restore(program,load_bound(path,h));s.advance(15);r.advance(15)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[20,23]
    assert [e['payload']['amount'] for e in hits]==pytest.approx([1300*.25999999046325684-100,1300*.25999999046325684-50])
    assert s.snapshot()==r.snapshot()==replay(program,s.export_replay()).snapshot()

def test_level1_leak_decrements_base2_but_leak_entity_count1():
    p=fixture();p['scenarioDraft']['initialEntities']=p['scenarioDraft']['initialEntities'][:1];p['scenarioDraft']['initialEntities'][0]['route']={'motionMode':0,'startPosition':{'row':3,'col':0},'endPosition':{'row':3,'col':0},'checkpoints':[]}
    p['scenarioDraft']['objectives']={'life_resource':'lives'};p['scenarioDraft']['resources']={'lives':{'initial':99999,'capacity':99999}};s=make(p);s.advance(2)
    assert s.ctx.state()['leaks']==1 and s.ctx.resources.current('system/battle','lives')==99997

def test_level1_lowHP_packet_uses_actual1950ATK_not_old1500():
    p=fixture(True);p['buffs'].append({'id':'buff/hold','kind':'buff','duration_seconds':1/30,'control':{'attack':False}})
    p['scenarioDraft']['initialEntities'][0]['components']={'buffs':{'initial':['buff/hold']}}
    s=make(p);s.submit({'action':'skill','source':'director','ability':'ability/hp14999'},at=0);s.advance(25)
    hits=[e for e in s.session.events if e['type']=='damage.accepted'];assert [e['time'] for e in hits]==[21,24]
    assert [e['payload']['amount'] for e in hits]==pytest.approx([1950*.25999999046325684-100,1950*.25999999046325684-50])
    assert s.snapshot()==replay(s.program,s.export_replay()).snapshot()
