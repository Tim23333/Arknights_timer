from pathlib import Path
import json
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound
ROOT=Path(__file__).resolve().parents[3]


def fixture(self_kill=False):
    p=json.loads((ROOT/'validation/campaign/m73_environment_peer/callback_reproduction/retire_second-fixture.json').read_bytes())
    p['abilities']=[];p['entities'][2]['components']['abilities']=[]
    p['rules'].append({'id':'rule/restore','kind':'rule','contract':'resource.recovery','implementation':{'type':'expression','expression':'inputs.parameters.capacity * inputs.parameters.ratio'}})
    p['entities'][0]['components']['rebirth']={'resource':'hp','max_count':1,'delay_seconds':.1,'restore_ratio':1,'restore_rule':'rule/restore'}
    p['entities'][0]['components']['resources']['hp'].update(initial=100,capacity=100)
    p['entities'][0]['components']['attributes']['base']['max_hp']=100
    if self_kill:p['entities'][0]['components']['rebirth']['on_begin']=[{'op':'instant_kill','target':'source','parameters':{'cause':'inner_self','skip_rebirth':True}}]
    return p


def test_environment_first_death_rebirth_then_final_no_source_claim_origin_cp_replay(tmp_path):
    s=Engine.create(Compiler().compile(fixture()),seed=79901);s.advance(5)
    assert s.ctx.alive('first') and not s.ctx.active('first')
    assert not [e for e in s.session.events if e['type']=='combat.kill']
    path=tmp_path/'cp.json';pin=write_ordered(path,s.checkpoint());r=Engine.restore(s.program,load_bound(path,pin));s.advance(15);r.advance(15)
    deaths=[e for e in s.session.events if e['type']=='combat.kill' and e['payload']['target']==2]
    assert len(deaths)==1 and deaths[0]['payload']['source'] is None
    assert deaths[0]['payload']['origin']['field_uid']=='field/1'
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_environment_initiates_rebirth_inner_actual_selfkill_claim_not_overwritten():
    s=Engine.create(Compiler().compile(fixture(True)),seed=79901);s.advance(5)
    deaths=[e for e in s.session.events if e['type']=='combat.kill' and e['payload']['target']==2]
    assert len(deaths)==1 and deaths[0]['payload']['source']==2
    assert s.ctx.get(2,('runtime','combat_death_claim','payload','source'))==2
