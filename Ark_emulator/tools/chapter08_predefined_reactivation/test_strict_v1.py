"""Typed registry/counter errors cannot acquire reactivation sideeffects."""
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from tools.chapter08_predefined_reactivation.test_generic_v1 import package

@pytest.mark.parametrize('change',[lambda r:r.update(activations=True),lambda r:r.update(current=True),
    lambda r:r.update(activations=-1),lambda r:r['template'].update(registration_key='other'),
    lambda r:r['template'].update(active=True)])
def test_corrupted_registry_counter_rejects_atomic(change):
    s=Engine.create(Compiler().compile(package()));data=s.ctx.state()['predefined_reactivation'];change(data['device1']);s.ctx.state_update(predefined_reactivation=data);before=s.checkpoint()
    with pytest.raises(ValueError):s.ctx.lifecycle.activate_predefined('device1')
    assert s.checkpoint()==before
