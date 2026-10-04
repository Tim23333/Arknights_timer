"""Actual public acknowledgements and checkpoint sidecar through tutorial waits."""
import json
from pathlib import Path
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.control_driver.public_ack_v2 import PublicAckDriver
from tools.campaign_ordered_checkpoint import write_ordered,load_bound

ROOT=Path(__file__).resolve().parents[2]


def package():
    p=json.loads((ROOT/'packages/campaign/chapter07_predefines_consumer/story.controls.v1.json').read_bytes())
    p['scenarioDraft']={'id':'scene/ch7/story_probe','ruleset':'ruleset/ark_standard',
        'map':{'rows':1,'cols':1},'objectives':{},'timeline':{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear',
        'waves':[{'fragments':[{'actions':[{'kind':'control','definition':p['controls'][0]['id'],
                                         'count':1,'delay_seconds':0,'interval_seconds':0,
                                         'managed':True}]}]}]}}
    return p


def test_four_popup_and_one_tutorial_public_acks_protect_and_fade(tmp_path):
    s=Engine.create(Compiler().compile(package()),seed=7186)
    driver=PublicAckDriver(s);driver.advance_to(3)
    cp=tmp_path/'story3.json';pin=write_ordered(cp,s.checkpoint());sidecar=driver.checkpoint()
    restored=Engine.restore(s.program,load_bound(cp,pin));continuation=PublicAckDriver(restored,sidecar)
    driver.advance_to(50);continuation.advance_to(50)
    assert s.checkpoint()==restored.checkpoint()==replay(s.program,s.export_replay()).checkpoint()
    assert driver.checkpoint()==continuation.checkpoint()
    assert len(driver.submitted)==5
    rows=[e for e in s.session.events if e['type']=='source.story.row']
    assert len(rows)==7
    tutorial=next(e for e in rows if e['payload']['command']=='Tutorial')
    waiting=[e for e in s.session.events if e['type']=='control.awaiting_ack']
    assert len(waiting)==5 and waiting[-1]['time']>=tutorial['time']+15
    complete=[e for e in s.session.events if e['type']=='control.completed']
    assert len(complete)==1 and not s.ctx.state().get('input_locks')
