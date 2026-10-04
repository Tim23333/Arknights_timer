"""Wave wake requests roll back together with the owning rebirth callback."""
from copy import deepcopy
import pytest
from ark_sim import Compiler,Engine
from tools.candidates.chapter07_foundation_v1.test_finish_timeline_wave_v1 import package,EFFECT


def test_begin_callback_late_fault_does_not_release_wave_or_leave_wake():
    p=package();unit=p['entities'][0];unit['components']['rebirth']={
        'resource':'hp','max_count':1,'delay_seconds':60,'restore_ratio':1,
        'restore_rule':'rule/wave/restore','on_begin':[deepcopy(EFFECT),
            {'op':'modify_resource','target':1,'resource':'missing','delta':1}]}
    p['rules']=[{'id':'rule/wave/restore','kind':'rule','contract':'resource.recovery',
                'implementation':{'type':'expression','expression':'inputs.parameters.capacity*inputs.parameters.ratio'}}]
    s=Engine.create(Compiler().compile(p));s.advance(1);before=s.checkpoint()
    with pytest.raises((ValueError,KeyError)):
        s.ctx.resources.adjust('source','hp',value=0)
    assert s.checkpoint()==before


def test_request_retained_source_cannot_cancel_other_wave_postdelay():
    p=package();p['scenarioDraft']['timeline']['waves'][0]['post_delay_seconds']=10/30
    s=Engine.create(Compiler().compile(p));s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=2)
    s.submit({'action':'skill','source':'source','ability':'ability/wave/release'},at=12)
    s.advance(23)
    assert s.ctx.alive('next')
    assert sum(e['type']=='timeline.wave_completed' for e in s.session.events)==1
