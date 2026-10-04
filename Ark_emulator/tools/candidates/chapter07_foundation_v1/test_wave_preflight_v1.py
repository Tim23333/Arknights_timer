"""Required wave runtime and actor owner must exist at compile time."""
from copy import deepcopy
import pytest
from ark_sim import Compiler
from tools.candidates.chapter07_foundation_v1.test_finish_timeline_wave_v1 import package,EFFECT


def test_source_with_no_timeline_cannot_compile_a_finish_request():
    p=package();p['scenarioDraft'].pop('timeline')
    p['scenarioDraft']['dependencies']=['unit/wave/source']
    with pytest.raises(ValueError,match='requires an actual scenario timeline'):
        Compiler().compile(p)


def test_control_battle_source_cannot_issue_actor_owned_wave_request():
    p=package();p['controls']=[{'id':'control/wave/invalid','kind':'control',
        'clock_policy':'logical','ack_policy':'immediate',
        'steps':[{'kind':'effects','effects':[deepcopy(EFFECT)]}]}]
    p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append(
        {'kind':'control','definition':'control/wave/invalid','managed':True})
    with pytest.raises(ValueError,match='actor-owned source'):
        Compiler().compile(p)
