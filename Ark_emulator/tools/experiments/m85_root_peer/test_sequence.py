from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.build_chapter04_bslime_model import build
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def fixture(two=True,camouflage=False):
    p=build();uid=p['entities'][0]['id']
    if two:p['entities'][0]['components']['lifecycle']['death_projectiles']*=2
    p['entities'].append({'id':'unit/hero','kind':'entity','tags':['player'],'components':{'spatial':{},
        'selection_state':{'side':0,'motion':1,'category':1,'abnormal_flags':[17] if camouflage else []},
        'attributes':{'base':{'max_hp':5000,'atk':3000,'def':100}},'resources':{'hp':{'initial':5000,'capacity':5000,'role':'health'}},'abilities':['ability/kill']}})
    p['selectors'].append({'id':'selector/kill','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'}],'limit':1})
    p['abilities'].append({'id':'ability/kill','kind':'ability','selector':'selector/kill','activation':{'mode':'manual'},'timeline':[{'at_seconds':0,'effect':{'op':'damage','damage_type':'true'}}]})
    p['scenarioDraft']={'id':'scene/seqpeer','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':3,'cols':4},'initialEntities':[
        {'definition':uid,'instanceAlias':'s','position':{'row':1,'col':1}}, {'definition':'unit/hero','instanceAlias':'h','position':{'row':1,'col':2}}]}
    s=Engine.create(Compiler().compile(p),seed=85031);s.submit({'action':'skill','source':'h','ability':'ability/kill'},at=1);return s


def ev(s,kind):return [e for e in s.session.events if e['type']==kind]


def test_two_real_source_packets_1040_each_apply_defense_each_cp_replay(tmp_path):
    s=fixture();s.session.advance(4);cp=tmp_path/'cp.json';pin=write_ordered(cp,s.checkpoint());r=Engine.restore(s.program,load_bound(cp,pin));s.session.advance(31);r.session.advance(31)
    assert len(ev(s,'projectile.launched'))==2 and s.ctx.resources.current('h','hp')==3120
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_first_packet_launch_callback_withdraw_stops_sequence_but_first_boom_survives(monkeypatch):
    s=fixture();original=s.ctx.buffs.toggles.pulse
    def callback(event,payload):
        original(event,payload)
        if event=='projectile.launched':s.ctx.lifecycle.retire('s','withdrawn')
    monkeypatch.setattr(s.ctx.buffs.toggles,'pulse',callback);s.session.advance(35)
    assert len(ev(s,'projectile.launched'))==1 and s.ctx.get('s',('runtime','state'))=='withdrawn'
    assert s.ctx.state()['kills']==0 and s.ctx.resources.current('h','hp')==4060


def test_native_ignore_camouflage1_hits_real_typed_camouflaged_ground_unit():
    s=fixture(two=False,camouflage=True);s.session.advance(35)
    assert s.ctx.resources.current('h','hp')==4060
