"""Keep native mine mode20, SP25 and explosion source order separate."""
import json
from pathlib import Path
from ark_sim import Compiler, Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered, load_bound

ROOT = Path(__file__).resolve().parents[2]


def package():
    p=json.loads((ROOT/'packages/campaign/chapter07_predefines_consumer/mine.module.v1.json').read_bytes())
    p['entities'].append({'id':'unit/mine/test/target','kind':'entity','tags':['enemy'],
        'components':{'attributes':{'base':{'max_hp':10000,'atk':0,'def':900,'mres':90}},
            'resources':{'hp':{'initial':10000,'capacity':10000,'role':'health'}},
            'selection_state':{'side':1,'motion':1,'category':1,'unit_type':2},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}})
    p['scenarioDraft']={'id':'scene/mine/test','ruleset':'ruleset/ark_standard',
        'map':{'rows':1,'cols':2},'objectives':{},'initialEntities':[
            {'definition':p['entities'][0]['id'],'instanceAlias':'mine','position':{'row':0,'col':0}},
            {'definition':'unit/mine/test/target','instanceAlias':'target','position':{'row':0,'col':.5}}]}
    return p


def test_native_mode20_does_not_bypass_SP25_normal_attack_nevertrigger():
    s=Engine.create(Compiler().compile(package()),seed=7182)
    s.advance(601)
    assert s.ctx.get('mine',('behavior','state'))=='mode1'
    assert not any(e['type']=='ability.started' for e in s.session.events)
    assert s.ctx.resources.current('mine','sp')<25
    s.advance(155)
    starts=[e for e in s.session.events if e['type']=='ability.started']
    packets=[e for e in s.session.events if e['type']=='damage.accepted']
    assert len(starts)==len(packets)==1
    assert starts[0]['time']==750 and packets[0]['time']==750
    assert packets[0]['payload']['amount']==3000
    assert s.ctx.resources.current('target','hp')==7000
    assert not s.ctx.alive('mine')
    assert packets[0]['payload']['damage_flags']=={'source_attack_type':'NORMAL','ignore_for_sp':False}


def test_real_checkpoint_before_readiness_and_head(tmp_path):
    s=Engine.create(Compiler().compile(package()),seed=7183)
    s.advance(599)
    path=tmp_path/'mode0.json';pin=write_ordered(path,s.checkpoint())
    r=Engine.restore(s.program,load_bound(path,pin))
    s.advance(157);r.advance(157)
    assert s.checkpoint()==r.checkpoint()==replay(s.program,s.export_replay()).checkpoint()
