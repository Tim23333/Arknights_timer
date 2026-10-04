"""Source numeric state, not tag spelling, drives the declared FLY_ONLY hook."""
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];RUNTIME=ROOT.parent/'unpack_work/campaign_m39_field_role_candidate'
sys.path.insert(0,str(RUNTIME))
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.experiments.chapter02_tiles.test_tile_buffs import fixture as old_fixture
from tools.build_chapter02_tile_motion_models import build


def fixture():
    p=old_fixture();typed=build();p['buffs']=typed['buffs'];p['rules']=typed['rules']
    for u in p['entities']:u['components']['selection_state']={'motion':2 if u['id']=='unit/fly' else 1}
    # Use actual chapter2 spelling and a source-independent probe marker for
    # target acquisition. The amplification rule reads only typed motion.
    p['entities'][2]['tags']=['enemy','fly','probe_target']
    next(s for s in p['selectors'] if s['id']=='selector/fly')['filters']=[{'tag':'probe_target'},{'state':'alive'}]
    return p


def test_ground_and_actual_fly_tag_obey_typed_state_and_exact_replay():
    p=fixture();s=Engine.create(Compiler().compile(p),seed=3901)
    for tick,ability in [(0,'ability/enter_gazebo'),(1,'ability/ground'),(2,'ability/fly')]:
        s.submit({'action':'skill','source':'source','ability':ability},at=tick)
    s.advance(3);assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[90,160]
    cp=s.checkpoint();r=Engine.restore(s.program,cp);s.advance(2);r.advance(2)
    assert s.snapshot()==r.snapshot()==replay(s.program,s.export_replay()).snapshot()


def test_flying_label_alone_cannot_amplify_a_ground_state():
    p=fixture();p['entities'][2]['components']['selection_state']['motion']=1;p['entities'][2]['tags'].append('flying')
    s=Engine.create(Compiler().compile(p),seed=3902)
    s.submit({'action':'skill','source':'source','ability':'ability/enter_gazebo'},at=0)
    s.submit({'action':'skill','source':'source','ability':'ability/fly'},at=1);s.advance(2)
    assert [e['payload']['amount'] for e in s.session.events if e['type']=='damage.accepted']==[90]
