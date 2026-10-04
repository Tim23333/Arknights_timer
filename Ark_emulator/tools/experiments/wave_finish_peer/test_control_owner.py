import pytest
from ark_sim import Compiler
from tools.experiments.wave_finish_peer.test_wave_bound import package,finish,INPUTS
def test_control_battle_effect_cannot_claim_actor_owned_wavefinish():
 p=package();p['controls']=[{'id':'control/w/foreign','kind':'control','clock_policy':'logical','ack_policy':'external','steps':[{'kind':'effects','effects':[finish()]}]}]
 p['scenarioDraft']['timeline']['waves'][0]['fragments'][0]['actions'].append({'kind':'control','definition':'control/w/foreign','managed':True,'blocks_wave':True,'blocks_fragment':False})
 INPUTS.append(p)
 with pytest.raises(ValueError):Compiler().compile(p)
